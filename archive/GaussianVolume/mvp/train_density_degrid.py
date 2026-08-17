"""P0 spatial-index evaluator and benchmark for density de-grid training."""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import math
import random
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from bake_directional_tau_basis import _sample_trilinear
from build_contracted_50k import GAUSSIAN_VOLUME, matrix_to_quaternion


WORK = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    WORK / "artifacts" / "wdas_404k_sigma038_aniso115" / "initializer.npz"
)
DEFAULT_GRID = (
    WORK.parents[1] / "tmp" / "wdas_cloud" / "grids" / "wdas_cloud_half.npy"
)
DEFAULT_OUTPUT = (
    WORK / "artifacts" / "wdas_density_degrid" / "p0_spatial_index"
)
DEFAULT_P1_OUTPUT = (
    WORK / "artifacts" / "wdas_density_degrid" / "p1_trainer_selfcheck"
)
DEFAULT_P2_OUTPUT = (
    WORK / "artifacts" / "wdas_density_degrid" / "p2_roi50k"
)
DEFAULT_P2B_OUTPUT = (
    WORK / "artifacts" / "wdas_density_degrid" / "p2b_roi30k_recovery"
)
DEFAULT_P2B_WARM_START = (
    DEFAULT_P2_OUTPUT / "round_02_030000" / "candidate.npz"
)
DEFAULT_P2B_PARENT_METRICS = (
    DEFAULT_P2_OUTPUT / "round_02_030000" / "metrics.json"
)
DEFAULT_P2C_OUTPUT = (
    WORK / "artifacts" / "wdas_density_degrid" / "p2c_40k_convergence"
)
DEFAULT_P2C_WARM_START = (
    DEFAULT_P2B_OUTPUT / "round_02_040000" / "candidate.npz"
)
DEFAULT_P2C_PARENT_METRICS = (
    DEFAULT_P2B_OUTPUT / "round_02_040000" / "metrics.json"
)
DEFAULT_P2C_FALLBACK = (
    DEFAULT_P2B_OUTPUT / "round_01_035000" / "candidate.npz"
)
DEFAULT_P2C_FALLBACK_METRICS = (
    DEFAULT_P2B_OUTPUT / "round_01_035000" / "metrics.json"
)
DEFAULT_DATASET = WORK / "artifacts" / "wdas_half_screen400k_tau8"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class SpatialIndex:
    origin: np.ndarray
    bin_size: float
    shape: tuple[int, int, int]
    cell_offsets: np.ndarray
    gaussian_ids: np.ndarray

    def to(self, device: torch.device) -> "TorchSpatialIndex":
        return TorchSpatialIndex(
            origin=torch.as_tensor(self.origin, dtype=torch.float32, device=device),
            bin_size=self.bin_size,
            shape=self.shape,
            cell_offsets=torch.as_tensor(
                self.cell_offsets, dtype=torch.int64, device=device
            ),
            gaussian_ids=torch.as_tensor(
                self.gaussian_ids, dtype=torch.int64, device=device
            ),
        )


@dataclass(frozen=True)
class TorchSpatialIndex:
    origin: torch.Tensor
    bin_size: float
    shape: tuple[int, int, int]
    cell_offsets: torch.Tensor
    gaussian_ids: torch.Tensor

    def pairs(self, samples: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        coordinates = torch.floor(
            (samples - self.origin) / self.bin_size
        ).to(torch.int64)
        limits = torch.as_tensor(
            self.shape, dtype=torch.int64, device=samples.device
        )
        valid = torch.all((coordinates >= 0) & (coordinates < limits), dim=1)
        sample_ids = torch.nonzero(valid, as_tuple=False).flatten()
        if not len(sample_ids):
            empty = torch.empty(0, dtype=torch.int64, device=samples.device)
            return empty, empty

        coordinates = coordinates[sample_ids]
        bins = (
            coordinates[:, 0]
            + self.shape[0]
            * (coordinates[:, 1] + self.shape[1] * coordinates[:, 2])
        )
        starts = self.cell_offsets[bins]
        counts = self.cell_offsets[bins + 1] - starts
        nonempty = counts > 0
        sample_ids = sample_ids[nonempty]
        starts = starts[nonempty]
        counts = counts[nonempty]
        pair_count = int(counts.sum().item())
        if pair_count == 0:
            empty = torch.empty(0, dtype=torch.int64, device=samples.device)
            return empty, empty

        pair_samples = torch.repeat_interleave(
            sample_ids, counts, output_size=pair_count
        )
        repeated_starts = torch.repeat_interleave(
            starts, counts, output_size=pair_count
        )
        repeated_prefix = torch.repeat_interleave(
            torch.cumsum(counts, dim=0) - counts,
            counts,
            output_size=pair_count,
        )
        positions = (
            repeated_starts
            + torch.arange(pair_count, device=samples.device)
            - repeated_prefix
        )
        return pair_samples, self.gaussian_ids[positions]


def build_spatial_index(
    centers: np.ndarray,
    covariances: np.ndarray,
    bin_size: float,
    support_sigma: float = 3.0,
    max_bins_per_gaussian: int = 256,
    motion_padding: float = 0.0,
) -> SpatialIndex:
    if (
        centers.ndim != 2
        or centers.shape[1:] != (3,)
        or covariances.shape != (len(centers), 3, 3)
        or len(centers) == 0
        or not np.isfinite(centers).all()
        or not np.isfinite(covariances).all()
        or bin_size <= 0.0
        or support_sigma <= 0.0
        or max_bins_per_gaussian <= 0
        or motion_padding < 0.0
    ):
        raise ValueError("invalid Gaussian arrays or spatial-index settings")

    axis_variance = np.diagonal(covariances, axis1=1, axis2=2)
    if np.any(axis_variance <= 0.0):
        raise ValueError("covariance diagonal must be positive")
    radius = support_sigma * np.sqrt(axis_variance) + motion_padding
    lower_world = centers - radius
    upper_world = centers + radius
    padding = bin_size * 1e-4
    origin = lower_world.min(axis=0) - padding
    shape_array = (
        np.floor((upper_world.max(axis=0) - origin) / bin_size).astype(np.int64)
        + 1
    )
    if np.prod(shape_array, dtype=np.int64) > np.iinfo(np.int32).max:
        raise ValueError("spatial index has too many cells")

    lower = np.floor((lower_world - origin) / bin_size).astype(np.int32)
    upper = np.floor((upper_world - origin) / bin_size).astype(np.int32)
    widths = upper - lower + 1
    counts = np.prod(widths.astype(np.int64), axis=1)
    if int(counts.max()) > max_bins_per_gaussian:
        raise ValueError(
            f"Gaussian covers {int(counts.max())} bins; "
            f"limit is {max_bins_per_gaussian}"
        )

    gaussian_ids = np.repeat(
        np.arange(len(centers), dtype=np.int32), counts
    )
    pair_count = len(gaussian_ids)
    pair_offsets = np.arange(pair_count, dtype=np.int64) - np.repeat(
        np.cumsum(counts) - counts, counts
    )
    pair_widths = widths[gaussian_ids].astype(np.int64)
    x = lower[gaussian_ids, 0].astype(np.int64) + pair_offsets % pair_widths[:, 0]
    pair_offsets //= pair_widths[:, 0]
    y = lower[gaussian_ids, 1].astype(np.int64) + pair_offsets % pair_widths[:, 1]
    z = lower[gaussian_ids, 2].astype(np.int64) + pair_offsets // pair_widths[:, 1]
    cell_ids = x + shape_array[0] * (y + shape_array[1] * z)
    order = np.argsort(cell_ids, kind="stable")
    cell_ids = cell_ids[order]
    gaussian_ids = gaussian_ids[order]
    cell_count = int(np.prod(shape_array, dtype=np.int64))
    occupancy = np.bincount(cell_ids, minlength=cell_count)
    cell_offsets = np.empty(cell_count + 1, dtype=np.int64)
    cell_offsets[0] = 0
    np.cumsum(occupancy, out=cell_offsets[1:])
    return SpatialIndex(
        origin=origin.astype(np.float32),
        bin_size=float(bin_size),
        shape=tuple(int(value) for value in shape_array),
        cell_offsets=cell_offsets,
        gaussian_ids=gaussian_ids,
    )


def evaluate_field(
    samples: torch.Tensor,
    centers: torch.Tensor,
    precisions: torch.Tensor,
    extinction: torch.Tensor,
    index: TorchSpatialIndex,
    support_sigma: float = 3.0,
) -> torch.Tensor:
    pair_samples, gaussian_ids = index.pairs(samples)
    field = torch.zeros(len(samples), dtype=samples.dtype, device=samples.device)
    if not len(pair_samples):
        return field
    delta = samples[pair_samples] - centers[gaussian_ids]
    mahalanobis2 = torch.einsum(
        "pi,pij,pj->p", delta, precisions[gaussian_ids], delta
    )
    contribution = extinction[gaussian_ids] * torch.exp(-0.5 * mahalanobis2)
    contribution = torch.where(
        mahalanobis2 <= support_sigma * support_sigma,
        contribution,
        torch.zeros_like(contribution),
    )
    return field.scatter_add(0, pair_samples, contribution)


def brute_field(
    samples: torch.Tensor,
    centers: torch.Tensor,
    precisions: torch.Tensor,
    extinction: torch.Tensor,
    support_sigma: float = 3.0,
) -> torch.Tensor:
    delta = samples[:, None] - centers[None]
    mahalanobis2 = torch.einsum("sgi,gij,sgj->sg", delta, precisions, delta)
    contribution = extinction[None] * torch.exp(-0.5 * mahalanobis2)
    return torch.where(
        mahalanobis2 <= support_sigma * support_sigma,
        contribution,
        torch.zeros_like(contribution),
    ).sum(dim=1)


def _inverse_softplus(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if np.any(values <= 0.0):
        raise ValueError("softplus initializer must be positive")
    return values + np.log(-np.expm1(-values))


def _quaternion_to_matrix(quaternion: torch.Tensor) -> torch.Tensor:
    quaternion = F.normalize(quaternion, dim=-1)
    x, y, z, w = quaternion.unbind(-1)
    xx, yy, zz = x * x, y * y, z * z
    xy, xz, yz = x * y, x * z, y * z
    wx, wy, wz = w * x, w * y, w * z
    return torch.stack(
        (
            1.0 - 2.0 * (yy + zz),
            2.0 * (xy - wz),
            2.0 * (xz + wy),
            2.0 * (xy + wz),
            1.0 - 2.0 * (xx + zz),
            2.0 * (yz - wx),
            2.0 * (xz - wy),
            2.0 * (yz + wx),
            1.0 - 2.0 * (xx + yy),
        ),
        dim=-1,
    ).reshape(-1, 3, 3)


class FreeGaussians(torch.nn.Module):
    """Unanchored center/log-scale/quaternion/extinction parameters."""

    def __init__(
        self,
        centers: np.ndarray,
        covariances: np.ndarray,
        extinction: np.ndarray,
        bounds: np.ndarray,
        min_scale: float,
        max_scale: float,
    ) -> None:
        super().__init__()
        eigenvalues, eigenvectors = np.linalg.eigh(covariances)
        if (
            centers.shape != (len(centers), 3)
            or covariances.shape != (len(centers), 3, 3)
            or extinction.shape != (len(centers),)
            or bounds.shape != (2, 3)
            or len(centers) == 0
            or np.any(eigenvalues <= 0.0)
            or np.any(extinction <= 0.0)
            or min_scale <= 0.0
            or max_scale < min_scale
            or np.any(bounds[1] <= bounds[0])
        ):
            raise ValueError("invalid free-Gaussian initializer")
        negative = np.linalg.det(eigenvectors) < 0.0
        eigenvectors[negative, :, 0] *= -1.0
        quaternions = np.asarray(
            [matrix_to_quaternion(matrix) for matrix in eigenvectors],
            dtype=np.float32,
        )
        self.center_m = torch.nn.Parameter(
            torch.as_tensor(centers, dtype=torch.float32)
        )
        self.log_scale_m = torch.nn.Parameter(
            torch.as_tensor(
                np.log(np.sqrt(eigenvalues)), dtype=torch.float32
            )
        )
        self.quaternion_xyzw = torch.nn.Parameter(
            torch.as_tensor(quaternions, dtype=torch.float32)
        )
        self.raw_sigma_t = torch.nn.Parameter(
            torch.as_tensor(
                _inverse_softplus(extinction), dtype=torch.float32
            )
        )
        self.register_buffer(
            "bounds_m", torch.as_tensor(bounds, dtype=torch.float32)
        )
        self.min_scale = float(min_scale)
        self.max_scale = float(max_scale)

    @classmethod
    def from_checkpoint_state(
        cls, state: dict, config: dict, device: torch.device
    ) -> "FreeGaussians":
        model = cls.__new__(cls)
        torch.nn.Module.__init__(model)
        model.center_m = torch.nn.Parameter(state["center_m"].to(device))
        model.log_scale_m = torch.nn.Parameter(state["log_scale_m"].to(device))
        model.quaternion_xyzw = torch.nn.Parameter(
            state["quaternion_xyzw"].to(device)
        )
        model.raw_sigma_t = torch.nn.Parameter(
            state["raw_sigma_t"].to(device)
        )
        model.register_buffer("bounds_m", state["bounds_m"].to(device))
        model.min_scale = float(config["min_scale"])
        model.max_scale = float(config["max_scale"])
        return model

    def kernels(
        self,
    ) -> tuple[
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
        torch.Tensor,
    ]:
        scales = torch.exp(self.log_scale_m)
        rotations = _quaternion_to_matrix(self.quaternion_xyzw)
        covariance = rotations @ (
            scales.square()[:, :, None] * rotations.transpose(1, 2)
        )
        precision = rotations @ (
            scales.square().reciprocal()[:, :, None]
            * rotations.transpose(1, 2)
        )
        extinction = F.softplus(self.raw_sigma_t)
        return self.center_m, covariance, precision, scales, extinction

    def mass(self) -> torch.Tensor:
        _, _, _, scales, extinction = self.kernels()
        return extinction * GAUSSIAN_VOLUME * scales.prod(dim=1)

    def optical_depth(
        self,
        origins: torch.Tensor,
        directions: torch.Tensor,
        chunk: int = 4096,
    ) -> torch.Tensor:
        centers, _, _, scales, extinction = self.kernels()
        rotations = _quaternion_to_matrix(self.quaternion_xyzw)
        result = torch.zeros(
            len(origins), dtype=origins.dtype, device=origins.device
        )
        for start in range(0, len(centers), chunk):
            stop = min(start + chunk, len(centers))
            rotation = rotations[start:stop]
            local_origin = torch.einsum(
                "bki,kij->bkj",
                origins[:, None] - centers[None, start:stop],
                rotation,
            )
            local_direction = torch.einsum(
                "bi,kij->bkj", directions, rotation
            )
            inverse_scale2 = scales[start:stop].square().reciprocal()
            along = torch.sum(
                local_direction.square() * inverse_scale2[None], dim=-1
            ).clamp_min(1e-10)
            linear = torch.sum(
                local_origin * local_direction * inverse_scale2[None], dim=-1
            )
            closest = (
                local_origin
                - (linear / along)[..., None] * local_direction
            )
            perpendicular = torch.sum(
                closest.square() * inverse_scale2[None], dim=-1
            ).clamp(0.0, 80.0)
            basis = (
                math.sqrt(2.0 * math.pi)
                * torch.rsqrt(along)
                * torch.exp(-0.5 * perpendicular)
            )
            result = result + torch.sum(
                basis * extinction[None, start:stop], dim=1
            )
        return result

    @torch.no_grad()
    def project_(self) -> None:
        self.center_m.clamp_(self.bounds_m[0], self.bounds_m[1])
        self.log_scale_m.clamp_(
            math.log(self.min_scale), math.log(self.max_scale)
        )
        self.quaternion_xyzw.copy_(
            F.normalize(self.quaternion_xyzw, dim=-1)
        )

    def checkpoint_state(self) -> dict:
        return {
            name: value.detach().cpu()
            for name, value in self.state_dict().items()
        }


class DensityGrid:
    """Memory-mapped source density with the project's grid/world transform."""

    def __init__(
        self,
        source: Path | np.ndarray,
        longest_size_m: float,
        density_scale_per_cm: float,
    ) -> None:
        grid = (
            np.load(source, mmap_mode="r")
            if isinstance(source, Path)
            else np.asarray(source)
        )
        grid = grid.squeeze()
        if (
            grid.ndim != 3
            or longest_size_m <= 0.0
            or density_scale_per_cm <= 0.0
            or not np.isfinite(grid).all()
            or np.min(grid) < 0.0
        ):
            raise ValueError("density grid must be finite, non-negative and 3D")
        self.grid = grid
        self.shape = np.asarray(grid.shape, dtype=np.int64)
        self.voxel_m = float(longest_size_m / np.max(self.shape))
        self.sigma_per_grid_unit = float(density_scale_per_cm * 100.0)

    def grid_to_world(self, coordinates: np.ndarray) -> np.ndarray:
        centered = np.asarray(coordinates, dtype=np.float32) - (
            self.shape.astype(np.float32) - 1.0
        ) * 0.5
        world = np.empty_like(centered)
        world[..., 0] = centered[..., 0]
        world[..., 1] = -centered[..., 2]
        world[..., 2] = -centered[..., 1]
        return world * self.voxel_m

    def world_to_grid(self, points: np.ndarray) -> np.ndarray:
        points = np.asarray(points, dtype=np.float32) / self.voxel_m
        coordinates = np.empty_like(points)
        coordinates[..., 0] = points[..., 0]
        coordinates[..., 1] = -points[..., 2]
        coordinates[..., 2] = -points[..., 1]
        return coordinates + (self.shape.astype(np.float32) - 1.0) * 0.5

    def sample_world(self, points: np.ndarray) -> np.ndarray:
        return (
            _sample_trilinear(self.grid, self.world_to_grid(points))
            * self.sigma_per_grid_unit
        )

    def bounds_world(self) -> np.ndarray:
        corners = np.asarray(
            np.meshgrid(
                *[(0.0, float(size - 1)) for size in self.shape],
                indexing="ij",
            )
        ).reshape(3, -1).T
        world = self.grid_to_world(corners)
        return np.stack((world.min(axis=0), world.max(axis=0)))

    def _voxel_candidates(
        self,
        generator: np.random.Generator,
        count: int,
        *,
        active: bool,
        edge_biased: bool = False,
        threshold: float = 1e-5,
        block_mask: np.ndarray | None = None,
        block_size: int = 8,
    ) -> np.ndarray:
        selected: list[np.ndarray] = []
        remaining = count
        attempts = 0
        allowed_cells = (
            np.argwhere(block_mask) if block_mask is not None else None
        )
        if allowed_cells is not None and not len(allowed_cells):
            raise ValueError("block mask contains no allowed cells")
        while remaining > 0 and attempts < 100:
            batch = max(remaining * (8 if active else 3), 1024)
            if allowed_cells is None:
                coordinates = np.column_stack(
                    [
                        generator.integers(0, int(size), size=batch)
                        for size in self.shape
                    ]
                )
            else:
                chosen_cells = allowed_cells[
                    generator.integers(0, len(allowed_cells), size=batch)
                ]
                coordinates = (
                    chosen_cells * block_size
                    + generator.integers(
                        0, block_size, size=(batch, 3)
                    )
                )
                coordinates = np.minimum(coordinates, self.shape - 1)
            values = self.grid[
                coordinates[:, 0], coordinates[:, 1], coordinates[:, 2]
            ]
            valid = values > threshold if active else values <= threshold
            if block_mask is not None and allowed_cells is None:
                blocks = np.minimum(
                    coordinates // block_size,
                    np.asarray(block_mask.shape) - 1,
                )
                valid &= block_mask[
                    blocks[:, 0], blocks[:, 1], blocks[:, 2]
                ]
            if edge_biased:
                clipped = np.clip(coordinates, 1, self.shape - 2)
                gradient = np.zeros(batch, dtype=np.float32)
                for axis in range(3):
                    lower = clipped.copy()
                    upper = clipped.copy()
                    lower[:, axis] -= 1
                    upper[:, axis] += 1
                    gradient += np.abs(
                        self.grid[
                            upper[:, 0], upper[:, 1], upper[:, 2]
                        ]
                        - self.grid[
                            lower[:, 0], lower[:, 1], lower[:, 2]
                        ]
                    )
                maximum = float(gradient.max())
                valid &= generator.random(batch) < (
                    gradient / max(maximum, 1e-12)
                )
            accepted = coordinates[valid][:remaining]
            if len(accepted):
                selected.append(accepted)
                remaining -= len(accepted)
            attempts += 1
        if remaining:
            raise RuntimeError(
                f"could not sample {count} qualifying voxels; {remaining} missing"
            )
        return np.concatenate(selected)

    def sample_training(
        self,
        generator: np.random.Generator,
        active_count: int,
        edge_count: int,
        empty_count: int,
        block_mask: np.ndarray | None = None,
        block_size: int = 8,
    ) -> tuple[np.ndarray, np.ndarray]:
        if min(active_count, edge_count, empty_count) < 0:
            raise ValueError("sample counts must be non-negative")
        groups = []
        for count, active, edge in (
            (active_count, True, False),
            (edge_count, True, True),
            (empty_count, False, False),
        ):
            if not count:
                continue
            voxels = self._voxel_candidates(
                generator,
                count,
                active=active,
                edge_biased=edge,
                block_mask=block_mask,
                block_size=block_size,
            )
            coordinates = np.clip(
                voxels
                + generator.uniform(-0.5, 0.5, size=voxels.shape),
                0.0,
                self.shape - 1.0,
            )
            groups.append(self.grid_to_world(coordinates))
        if not groups:
            raise ValueError("at least one training sample is required")
        points = np.concatenate(groups).astype(np.float32)
        order = generator.permutation(len(points))
        points = points[order]
        return points, self.sample_world(points).astype(np.float32)

    def local_covariances(
        self,
        points: np.ndarray,
        min_scale: float,
        max_scale: float,
        radius_voxels: float = 1.0,
    ) -> np.ndarray:
        if (
            min_scale <= 0.0
            or max_scale < min_scale
            or radius_voxels <= 0.0
        ):
            raise ValueError("invalid local covariance scales")
        coordinates = self.world_to_grid(points)
        offsets = [(0.0, 0.0, 0.0)]
        for axis in range(3):
            for sign in (-1.0, 1.0):
                offset = np.zeros(3)
                offset[axis] = sign * radius_voxels
                offsets.append(tuple(offset))
        for first in range(3):
            for second in range(first + 1, 3):
                for first_sign in (-1.0, 1.0):
                    for second_sign in (-1.0, 1.0):
                        offset = np.zeros(3)
                        offset[first] = first_sign * radius_voxels
                        offset[second] = second_sign * radius_voxels
                        offsets.append(tuple(offset))
        offset_array = np.asarray(offsets, dtype=np.float32)
        queries = coordinates[:, None, :] + offset_array[None]
        values = _sample_trilinear(
            self.grid, queries.reshape(-1, 3)
        ).reshape(len(points), len(offsets))
        log_density = np.log1p(
            values * self.sigma_per_grid_unit
        )
        step_m = radius_voxels * self.voxel_m
        hessian = np.zeros((len(points), 3, 3), dtype=np.float64)
        center = log_density[:, 0]
        for axis in range(3):
            lower = 1 + axis * 2
            hessian[:, axis, axis] = (
                log_density[:, lower]
                - 2.0 * center
                + log_density[:, lower + 1]
            ) / step_m**2
        offset_index = 7
        for first in range(3):
            for second in range(first + 1, 3):
                mm, mp, pm, pp = (
                    log_density[:, offset_index + index] for index in range(4)
                )
                mixed = (pp - pm - mp + mm) / (4.0 * step_m**2)
                hessian[:, first, second] = mixed
                hessian[:, second, first] = mixed
                offset_index += 4
        eigenvalues, eigenvectors = np.linalg.eigh(-hessian)
        curvature = np.clip(
            eigenvalues, 1.0 / max_scale**2, 1.0 / min_scale**2
        )
        covariance = eigenvectors @ (
            (1.0 / curvature)[:, :, None]
            * np.transpose(eigenvectors, (0, 2, 1))
        )
        return covariance.astype(np.float32)


@dataclass(frozen=True)
class FrozenField:
    centers: torch.Tensor
    precisions: torch.Tensor
    extinction: torch.Tensor
    index: TorchSpatialIndex

    @classmethod
    def from_arrays(
        cls,
        centers: np.ndarray,
        covariances: np.ndarray,
        extinction: np.ndarray,
        device: torch.device,
        bin_size: float,
        support_sigma: float,
        max_bins_per_gaussian: int,
    ) -> "FrozenField":
        index = build_spatial_index(
            centers,
            covariances,
            bin_size,
            support_sigma,
            max_bins_per_gaussian,
        ).to(device)
        return cls(
            centers=torch.as_tensor(
                centers, dtype=torch.float32, device=device
            ),
            precisions=torch.as_tensor(
                np.linalg.inv(covariances),
                dtype=torch.float32,
                device=device,
            ),
            extinction=torch.as_tensor(
                extinction, dtype=torch.float32, device=device
            ),
            index=index,
        )

    def evaluate(
        self, samples: torch.Tensor, support_sigma: float
    ) -> torch.Tensor:
        return evaluate_field(
            samples,
            self.centers,
            self.precisions,
            self.extinction,
            self.index,
            support_sigma,
        )

    def optical_depth(
        self,
        origins: torch.Tensor,
        directions: torch.Tensor,
        chunk: int = 4096,
    ) -> torch.Tensor:
        result = torch.zeros(
            len(origins), dtype=origins.dtype, device=origins.device
        )
        for start in range(0, len(self.centers), chunk):
            stop = min(start + chunk, len(self.centers))
            offset = (
                origins[:, None] - self.centers[None, start:stop]
            )
            precision = self.precisions[start:stop]
            along = torch.einsum(
                "bi,kij,bj->bk", directions, precision, directions
            ).clamp_min(1e-10)
            linear = torch.einsum(
                "bki,kij,bj->bk", offset, precision, directions
            )
            constant = torch.einsum(
                "bki,kij,bkj->bk", offset, precision, offset
            )
            perpendicular = (
                constant - linear.square() / along
            ).clamp(0.0, 80.0)
            basis = (
                math.sqrt(2.0 * math.pi)
                * torch.rsqrt(along)
                * torch.exp(-0.5 * perpendicular)
            )
            result = result + torch.sum(
                basis * self.extinction[None, start:stop], dim=1
            )
        return result


def select_weighted_seeds(
    points: np.ndarray,
    target_density: np.ndarray,
    covariances: np.ndarray,
    count: int,
    min_distance: float,
    generator: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if (
        points.shape != (len(target_density), 3)
        or covariances.shape != (len(target_density), 3, 3)
        or count <= 0
        or count > len(points)
        or min_distance <= 0.0
        or np.any(target_density <= 0.0)
    ):
        raise ValueError("invalid weighted seed candidates")
    keys = np.log(
        generator.random(len(points)).clip(np.finfo(np.float64).tiny, 1.0)
    ) / target_density
    occupied: set[tuple[int, int, int]] = set()
    selected: list[int] = []
    for index in np.argsort(keys, kind="stable")[::-1]:
        cell = tuple(
            np.floor(points[index] / min_distance).astype(np.int64)
        )
        if cell in occupied:
            continue
        occupied.add(cell)
        selected.append(int(index))
        if len(selected) == count:
            break
    if len(selected) != count:
        raise RuntimeError(
            f"only found {len(selected)} separated seeds for {count} points"
        )
    indices = np.asarray(selected, dtype=np.int64)
    return points[indices], covariances[indices], target_density[indices]


def make_optimizer(
    model: FreeGaussians,
    geometry_lr: float = 2e-3,
    extinction_lr: float = 1e-3,
) -> torch.optim.Adam:
    if min(geometry_lr, extinction_lr) <= 0.0:
        raise ValueError("learning rates must be positive")
    return torch.optim.Adam(
        (
            {
                "params": (
                    model.center_m,
                    model.log_scale_m,
                    model.quaternion_xyzw,
                ),
                "lr": geometry_lr,
            },
            {"params": (model.raw_sigma_t,), "lr": extinction_lr},
        )
    )


def density_losses(
    prediction: torch.Tensor,
    target: torch.Tensor,
    candidate_mass: torch.Tensor,
    reference_mass: float,
    active_threshold: float = 1e-4,
    empty_threshold: float = 1e-5,
) -> dict[str, torch.Tensor]:
    if reference_mass <= 0.0:
        raise ValueError("reference mass must be positive")
    predicted_log = torch.log1p(prediction)
    target_log = torch.log1p(target)
    density = F.smooth_l1_loss(predicted_log, target_log, beta=0.1)
    active = target > active_threshold
    coverage = (
        F.relu(target_log[active] - predicted_log[active]).square().mean()
        if bool(active.any())
        else prediction.new_zeros(())
    )
    empty = target <= empty_threshold
    empty_space = (
        torch.log1p(prediction[empty]).mean()
        if bool(empty.any())
        else prediction.new_zeros(())
    )
    mass = torch.log(
        candidate_mass.sum().clamp_min(1e-12) / reference_mass
    ).square()
    return {
        "density": density,
        "coverage": coverage,
        "empty": empty_space,
        "mass": mass,
    }


def ray_losses(
    prediction: torch.Tensor,
    target: torch.Tensor,
    patch_size: int,
) -> dict[str, torch.Tensor]:
    from recover_contracted_50k import _edge_loss, _frequency_loss

    if prediction.shape != target.shape or patch_size < 3:
        raise ValueError("ray prediction/target or patch size is invalid")
    tau = F.smooth_l1_loss(
        torch.log1p(prediction), torch.log1p(target), beta=0.1
    )
    transmittance = (
        torch.exp(-prediction) - torch.exp(-target)
    ).abs().mean()
    edge = _edge_loss(prediction, target, patch_size)
    frequency = (
        _frequency_loss(prediction, target, patch_size)
        if patch_size >= 5
        else prediction.new_zeros(())
    )
    return {
        "tau": tau,
        "transmittance": transmittance,
        "edge": edge,
        "frequency": frequency,
    }


def evaluate_hybrid(
    frozen: FrozenField,
    dynamic: FrozenField | FreeGaussians,
    origins: np.ndarray,
    directions: np.ndarray,
    optical_depth: np.ndarray,
    patch_centers: np.ndarray,
    device: torch.device,
    patch_radius: int = 2,
) -> dict:
    from evaluate_heldout import compute_metrics
    from recover_contracted_50k import (
        _edge_loss,
        _frequency_loss,
        _gather_patches,
    )

    ray_origins, ray_directions, target = _gather_patches(
        origins,
        directions,
        optical_depth,
        patch_centers,
        radius=patch_radius,
    )
    predictions = []
    with torch.no_grad():
        for start in range(0, len(target), 18):
            origins_t = torch.as_tensor(
                ray_origins[start : start + 18],
                dtype=torch.float32,
                device=device,
            )
            directions_t = torch.as_tensor(
                ray_directions[start : start + 18],
                dtype=torch.float32,
                device=device,
            )
            predictions.append(
                (
                    frozen.optical_depth(origins_t, directions_t)
                    + dynamic.optical_depth(origins_t, directions_t)
                ).cpu()
            )
    prediction = torch.cat(predictions)
    target_tensor = torch.as_tensor(target, dtype=torch.float32)
    metrics = compute_metrics(
        np.exp(-target), prediction.numpy(), alpha_threshold=1e-4
    )
    patch_size = patch_radius * 2 + 1
    metrics["edge_l1"] = float(
        _edge_loss(prediction, target_tensor, patch_size)
    )
    metrics["gabor_energy_l1"] = float(
        _frequency_loss(
            prediction, target_tensor, patch_size, phase_weight=0.0
        )
    )
    metrics["gabor_phase_energy_l1"] = float(
        _frequency_loss(prediction, target_tensor, patch_size)
    )
    return metrics


def quality_strict(metrics: dict, baseline: dict) -> bool:
    return (
        metrics["tau_psnr_db"] >= baseline["tau_psnr_db"]
        and metrics["tau_mae"] <= baseline["tau_mae"]
        and metrics["transmittance_psnr_foreground_db"]
        >= baseline["transmittance_psnr_foreground_db"]
        and metrics["edge_l1"] <= baseline["edge_l1"]
        and metrics["gabor_energy_l1"] <= baseline["gabor_energy_l1"]
        and metrics["gabor_phase_energy_l1"]
        <= baseline["gabor_phase_energy_l1"]
        and metrics["silhouette_iou"] >= baseline["silhouette_iou"]
    )


def quality_bounded(metrics: dict, baseline: dict) -> bool:
    return (
        metrics["tau_psnr_db"] >= baseline["tau_psnr_db"] - 0.05
        and metrics["tau_mae"] <= baseline["tau_mae"] * 1.005
        and metrics["transmittance_psnr_foreground_db"]
        >= baseline["transmittance_psnr_foreground_db"] - 0.05
        and metrics["edge_l1"] <= baseline["edge_l1"] * 1.005
        and metrics["gabor_energy_l1"]
        <= baseline["gabor_energy_l1"] * 1.005
        and metrics["gabor_phase_energy_l1"]
        <= baseline["gabor_phase_energy_l1"] * 1.005
        and metrics["silhouette_iou"]
        >= baseline["silhouette_iou"] - 0.0011
    )


def roi_quality_gate(metrics: dict, baseline: dict) -> bool:
    return (
        metrics["tau_mae"] <= baseline["tau_mae"] * 1.005
        and metrics["edge_l1"] <= baseline["edge_l1"] * 1.005
    )


def recovery_progress(
    global_metrics: dict,
    roi_metrics: dict,
    previous_global: dict,
    previous_roi: dict,
    baseline: dict,
) -> dict:
    global_tau_ok = (
        global_metrics["tau_mae"] <= previous_global["tau_mae"] * 1.005
    )
    roi_tau_ok = roi_metrics["tau_mae"] <= previous_roi["tau_mae"] * 1.005
    return {
        "global_tau_nonregression": global_tau_ok,
        "roi_tau_nonregression": roi_tau_ok,
        "global_edge_nonregression": (
            global_metrics["edge_l1"]
            <= previous_global["edge_l1"] * 1.005
        ),
        "roi_edge_nonregression": (
            roi_metrics["edge_l1"] <= previous_roi["edge_l1"] * 1.005
        ),
        "joint_tau_regression": not global_tau_ok and not roi_tau_ok,
        "score": sum(
            (
                global_metrics["tau_mae"] / baseline["global"]["tau_mae"],
                global_metrics["edge_l1"] / baseline["global"]["edge_l1"],
                roi_metrics["tau_mae"] / baseline["roi"]["tau_mae"],
                roi_metrics["edge_l1"] / baseline["roi"]["edge_l1"],
            )
        ),
    }


def _enforce_allowed_region(
    model: FreeGaussians,
    before: torch.Tensor,
    allowed_region: tuple[DensityGrid, np.ndarray, int] | None,
) -> int:
    if allowed_region is None:
        return 0
    source, block_mask, block_size = allowed_region
    coordinates = source.world_to_grid(
        model.center_m.detach().cpu().numpy()
    )
    blocks = np.floor(
        (coordinates + 1e-4) / block_size
    ).astype(np.int64)
    block_shape = np.asarray(block_mask.shape)
    inside = np.all((blocks >= 0) & (blocks < block_shape), axis=1)
    valid = np.zeros(len(blocks), dtype=bool)
    valid_blocks = blocks[inside]
    valid[inside] = block_mask[
        valid_blocks[:, 0], valid_blocks[:, 1], valid_blocks[:, 2]
    ]
    invalid = torch.as_tensor(~valid, device=model.center_m.device)
    with torch.no_grad():
        model.center_m[invalid] = before[invalid]
    return int(invalid.sum())


def density_step(
    model: FreeGaussians,
    optimizer: torch.optim.Optimizer,
    samples: torch.Tensor,
    target: torch.Tensor,
    reference_mass: float,
    bin_size: float,
    support_sigma: float,
    max_bins_per_gaussian: int,
    weights: dict[str, float] | None = None,
    frozen: FrozenField | None = None,
    allowed_region: tuple[DensityGrid, np.ndarray, int] | None = None,
) -> dict:
    weights = weights or {
        "density": 1.0,
        "coverage": 1.0,
        "empty": 0.1,
        "mass": 0.1,
    }
    before = model.center_m.detach().clone()
    centers, covariance, precision, _, extinction = model.kernels()
    index = build_spatial_index(
        centers.detach().cpu().numpy(),
        covariance.detach().cpu().numpy(),
        bin_size,
        support_sigma,
        max_bins_per_gaussian,
    ).to(samples.device)
    prediction = evaluate_field(
        samples, centers, precision, extinction, index, support_sigma
    )
    if frozen is not None:
        prediction = prediction + frozen.evaluate(samples, support_sigma)
    losses = density_losses(
        prediction, target, model.mass(), reference_mass
    )
    loss = sum(weights[name] * losses[name] for name in losses)
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
    optimizer.step()
    model.project_()
    reverted = _enforce_allowed_region(model, before, allowed_region)
    center_shift = torch.linalg.vector_norm(
        model.center_m.detach() - before, dim=1
    )
    error = (
        torch.log1p(prediction.detach()) - torch.log1p(target)
    ).abs()
    return {
        "loss": float(loss.detach()),
        **{name: float(value.detach()) for name, value in losses.items()},
        "center_shift_max_m": float(center_shift.max()),
        "center_shift_p50_m": float(center_shift.median()),
        "center_reverted_outside_allowed_region": reverted,
        "error": error.cpu().numpy(),
        "prediction": prediction.detach().cpu().numpy(),
    }


def ray_step(
    model: FreeGaussians,
    optimizer: torch.optim.Optimizer,
    frozen: FrozenField,
    ray_origins: np.ndarray,
    ray_directions: np.ndarray,
    target_tau: np.ndarray,
    reference_mass: float,
    allowed_region: tuple[DensityGrid, np.ndarray, int],
) -> dict:
    before = model.center_m.detach().clone()
    origins = torch.as_tensor(
        ray_origins, dtype=torch.float32, device=model.center_m.device
    )
    directions = torch.as_tensor(
        ray_directions, dtype=torch.float32, device=model.center_m.device
    )
    target = torch.as_tensor(
        target_tau, dtype=torch.float32, device=model.center_m.device
    )
    prediction = frozen.optical_depth(
        origins, directions
    ) + model.optical_depth(origins, directions)
    losses = ray_losses(prediction, target, patch_size=5)
    mass = torch.log(
        model.mass().sum().clamp_min(1e-12) / reference_mass
    ).square()
    loss = (
        losses["tau"]
        + 4.0 * losses["transmittance"]
        + 6.0 * losses["edge"]
        + 2.0 * losses["frequency"]
        + 0.5 * mass
    )
    optimizer.zero_grad(set_to_none=True)
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
    optimizer.step()
    model.project_()
    reverted = _enforce_allowed_region(
        model, before, allowed_region
    )
    shift = torch.linalg.vector_norm(
        model.center_m.detach() - before, dim=1
    )
    return {
        "loss": float(loss.detach()),
        **{name: float(value.detach()) for name, value in losses.items()},
        "mass": float(mass.detach()),
        "center_shift_max_m": float(shift.max()),
        "center_reverted_outside_allowed_region": reverted,
    }


def densify_prune(
    model: FreeGaussians,
    error_positions: np.ndarray,
    errors: np.ndarray,
    residual_extinction: np.ndarray,
    new_covariances: np.ndarray,
    target_count: int,
    max_new: int,
    min_distance: float,
) -> tuple[FreeGaussians, dict]:
    if (
        error_positions.shape != (len(errors), 3)
        or residual_extinction.shape != (len(errors),)
        or new_covariances.shape != (len(errors), 3, 3)
        or target_count <= 0
        or max_new <= 0
        or min_distance <= 0.0
    ):
        raise ValueError("invalid densification inputs")
    current_count = len(model.center_m)
    required_growth = max(target_count - current_count, 0)
    if max_new < required_growth:
        raise ValueError("max_new cannot reach the target count")
    new_count = min(max_new, target_count)
    keep_count = target_count - new_count
    if keep_count > current_count:
        raise ValueError("densification schedule cannot keep enough old points")

    with torch.no_grad():
        centers, covariance, _, _, extinction = model.kernels()
        mass = model.mass()
    keep = torch.topk(mass, keep_count, sorted=False).indices.cpu().numpy()
    old_centers = centers.detach().cpu().numpy()
    old_covariances = covariance.detach().cpu().numpy()
    old_extinction = extinction.detach().cpu().numpy()
    occupied = {
        tuple(cell)
        for cell in np.floor(old_centers[keep] / min_distance).astype(np.int64)
    }
    selected: list[int] = []
    for index in np.argsort(errors, kind="stable")[::-1]:
        cell = tuple(
            np.floor(error_positions[index] / min_distance).astype(np.int64)
        )
        if cell in occupied:
            continue
        occupied.add(cell)
        selected.append(int(index))
        if len(selected) == new_count:
            break
    if len(selected) != new_count:
        raise RuntimeError(
            f"only found {len(selected)} separated error samples for "
            f"{new_count} new points"
        )
    selected_array = np.asarray(selected, dtype=np.int64)
    centers_out = np.concatenate(
        (old_centers[keep], error_positions[selected_array])
    )
    covariance_out = np.concatenate(
        (old_covariances[keep], new_covariances[selected_array])
    )
    extinction_out = np.concatenate(
        (
            old_extinction[keep],
            np.maximum(residual_extinction[selected_array], 1e-8),
        )
    )
    replacement = FreeGaussians(
        centers_out,
        covariance_out,
        extinction_out,
        model.bounds_m.detach().cpu().numpy(),
        model.min_scale,
        model.max_scale,
    ).to(model.center_m.device)
    replacement.project_()
    return replacement, {
        "before": current_count,
        "kept": keep_count,
        "added": new_count,
        "after": len(replacement.center_m),
        "selected_error_p50_p95": np.percentile(
            errors[selected_array], (50, 95)
        ).tolist(),
    }


@torch.no_grad()
def normalize_mass_(
    model: FreeGaussians, reference_mass: float
) -> float:
    current_mass = float(model.mass().sum())
    if min(current_mass, reference_mass) <= 0.0:
        raise ValueError("mass normalization requires positive mass")
    _, _, _, _, extinction = model.kernels()
    scaled = (extinction * (reference_mass / current_mass)).cpu().numpy()
    model.raw_sigma_t.copy_(
        torch.as_tensor(
            _inverse_softplus(scaled),
            dtype=torch.float32,
            device=model.raw_sigma_t.device,
        )
    )
    return current_mass / reference_mass


def save_model_npz(model: FreeGaussians, path: Path) -> None:
    with torch.no_grad():
        centers, covariance, _, _, extinction = model.kernels()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            center_m=centers.detach().cpu().numpy().astype(np.float32),
            covariance_m2=covariance.detach().cpu().numpy().astype(np.float32),
            sigma_t_per_m=extinction.detach().cpu().numpy().astype(np.float32),
        )
    temporary.replace(path)


def save_hybrid_npz(
    initializer: Path,
    roi_indices_path: Path,
    candidate: Path,
    output: Path,
) -> dict:
    with np.load(initializer) as source, np.load(candidate) as trained:
        centers = np.asarray(source["center_m"], dtype=np.float32)
        covariance = np.asarray(source["covariance_m2"], dtype=np.float32)
        extinction = np.asarray(source["sigma_t_per_m"], dtype=np.float32)
        candidate_centers = np.asarray(trained["center_m"], dtype=np.float32)
        candidate_covariance = np.asarray(
            trained["covariance_m2"], dtype=np.float32
        )
        candidate_extinction = np.asarray(
            trained["sigma_t_per_m"], dtype=np.float32
        )
    roi_indices = np.load(roi_indices_path)
    if (
        roi_indices.ndim != 1
        or len(np.unique(roi_indices)) != len(roi_indices)
        or np.any(roi_indices < 0)
        or np.any(roi_indices >= len(centers))
    ):
        raise ValueError("ROI indices are invalid")
    outside = np.ones(len(centers), dtype=bool)
    outside[roi_indices] = False
    hybrid_centers = np.concatenate((centers[outside], candidate_centers))
    hybrid_covariance = np.concatenate(
        (covariance[outside], candidate_covariance)
    )
    hybrid_extinction = np.concatenate(
        (extinction[outside], candidate_extinction)
    )
    eigenvalues = np.linalg.eigvalsh(hybrid_covariance)
    if (
        not all(
            np.isfinite(value).all()
            for value in (
                hybrid_centers,
                hybrid_covariance,
                hybrid_extinction,
            )
        )
        or np.any(hybrid_extinction <= 0.0)
        or np.any(eigenvalues <= 0.0)
    ):
        raise ValueError("hybrid candidate is not structurally valid")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("wb") as stream:
        np.savez_compressed(
            stream,
            center_m=hybrid_centers,
            covariance_m2=hybrid_covariance,
            sigma_t_per_m=hybrid_extinction,
        )
    temporary.replace(output)
    return {
        "initializer": str(initializer.resolve()),
        "initializer_sha256": _sha256(initializer),
        "roi_indices": str(roi_indices_path.resolve()),
        "roi_indices_sha256": _sha256(roi_indices_path),
        "candidate": str(candidate.resolve()),
        "candidate_sha256": _sha256(candidate),
        "frozen_count": int(outside.sum()),
        "candidate_count": len(candidate_centers),
        "combined_count": len(hybrid_centers),
        "minimum_extinction": float(hybrid_extinction.min()),
        "minimum_covariance_eigenvalue": float(eigenvalues.min()),
        "output": str(output.resolve()),
        "output_sha256": _sha256(output),
    }


def initialize_p2_candidate(
    source: DensityGrid,
    frozen: FrozenField,
    core_mask: np.ndarray,
    block_size: int,
    count: int,
    reference_mass: float,
    generator: np.random.Generator,
    device: torch.device,
) -> tuple[FreeGaussians, dict]:
    pool_count = max(count * 8, 2048)
    pool_points, pool_target = source.sample_training(
        generator,
        active_count=pool_count // 2,
        edge_count=pool_count // 2,
        empty_count=0,
        block_mask=core_mask,
        block_size=block_size,
    )
    with torch.no_grad():
        pool_frozen = frozen.evaluate(
            torch.as_tensor(
                pool_points, dtype=torch.float32, device=device
            ),
            3.0,
        ).cpu().numpy()
    residual = np.maximum(pool_target - pool_frozen, 1e-6)
    pool_covariance = source.local_covariances(
        pool_points,
        min_scale=source.voxel_m * 0.5,
        max_scale=0.06,
    )
    centers, covariance, extinction = select_weighted_seeds(
        pool_points,
        residual,
        pool_covariance,
        count=count,
        min_distance=source.voxel_m * 1.25,
        generator=generator,
    )
    model = FreeGaussians(
        centers,
        covariance,
        extinction,
        source.bounds_world().astype(np.float32),
        min_scale=source.voxel_m * 0.25,
        max_scale=0.065,
    ).to(device)
    pre_normalization_mass_ratio = normalize_mass_(model, reference_mass)
    return model, {
        "candidate_count": count,
        "pool_count": pool_count,
        "residual_p01_p50_p99": np.percentile(
            residual, (1, 50, 99)
        ).tolist(),
        "pre_normalization_mass_ratio": pre_normalization_mass_ratio,
    }


def densify_p2_candidate(
    model: FreeGaussians,
    frozen: FrozenField,
    source: DensityGrid,
    halo_mask: np.ndarray,
    block_size: int,
    target_count: int,
    reference_mass: float,
    generator: np.random.Generator,
    device: torch.device,
    sample_count: int,
) -> tuple[FreeGaussians, dict]:
    points, target = source.sample_training(
        generator,
        active_count=sample_count // 2,
        edge_count=sample_count // 2,
        empty_count=0,
        block_mask=halo_mask,
        block_size=block_size,
    )
    with torch.no_grad():
        centers, covariance, precision, _, extinction = model.kernels()
        index = build_spatial_index(
            centers.detach().cpu().numpy(),
            covariance.detach().cpu().numpy(),
            0.1,
            3.0,
            256,
        ).to(device)
        points_t = torch.as_tensor(
            points, dtype=torch.float32, device=device
        )
        prediction = (
            frozen.evaluate(points_t, 3.0)
            + evaluate_field(
                points_t,
                centers,
                precision,
                extinction,
                index,
                3.0,
            )
        ).cpu().numpy()
    errors = np.abs(np.log1p(prediction) - np.log1p(target))
    covariance = source.local_covariances(
        points,
        min_scale=source.voxel_m * 0.5,
        max_scale=0.06,
    )
    replacement, report = densify_prune(
        model,
        points,
        errors,
        np.maximum(target - prediction, 1e-6),
        covariance,
        target_count=target_count,
        max_new=target_count - len(model.center_m),
        min_distance=source.voxel_m * 1.25,
    )
    report["pre_normalization_mass_ratio"] = normalize_mass_(
        replacement, reference_mass
    )
    return replacement, report


def _rng_state(generator: np.random.Generator) -> dict:
    return {
        "python": random.getstate(),
        "numpy_generator": generator.bit_generator.state,
        "torch_cpu": torch.get_rng_state(),
        "torch_cuda": (
            torch.cuda.get_rng_state_all() if torch.cuda.is_available() else []
        ),
    }


def _restore_rng(state: dict) -> np.random.Generator:
    random.setstate(state["python"])
    generator = np.random.default_rng()
    generator.bit_generator.state = state["numpy_generator"]
    torch.set_rng_state(state["torch_cpu"].cpu())
    if torch.cuda.is_available() and state["torch_cuda"]:
        torch.cuda.set_rng_state_all(
            [value.cpu() for value in state["torch_cuda"]]
        )
    return generator


def save_checkpoint(
    path: Path,
    model: FreeGaussians,
    optimizer: torch.optim.Optimizer,
    generator: np.random.Generator,
    *,
    phase: str,
    round_index: int,
    step: int,
    densification_state: dict,
    hashes: dict[str, str],
    index_settings: dict,
) -> None:
    payload = {
        "phase": phase,
        "round": round_index,
        "step": step,
        "model": model.checkpoint_state(),
        "model_config": {
            "min_scale": model.min_scale,
            "max_scale": model.max_scale,
        },
        "optimizer": optimizer.state_dict(),
        "densification_state": densification_state,
        "rng": _rng_state(generator),
        "hashes": hashes,
        "point_count": len(model.center_m),
        "index_settings": index_settings,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(payload, temporary)
    temporary.replace(path)


def load_checkpoint(
    path: Path,
    device: torch.device,
    expected_hashes: dict[str, str],
    geometry_lr: float,
    extinction_lr: float,
) -> tuple[FreeGaussians, torch.optim.Adam, np.random.Generator, dict]:
    payload = torch.load(path, map_location=device, weights_only=False)
    if payload["hashes"] != expected_hashes:
        raise ValueError("checkpoint source hashes do not match")
    model = FreeGaussians.from_checkpoint_state(
        payload["model"], payload["model_config"], device
    )
    optimizer = make_optimizer(model, geometry_lr, extinction_lr)
    optimizer.load_state_dict(payload["optimizer"])
    generator = _restore_rng(payload["rng"])
    return model, optimizer, generator, payload


def self_check() -> dict:
    dtype = np.float32
    centers_np = np.asarray(
        ((0.0, 0.0, 0.0), (0.22, -0.03, 0.02), (-0.15, 0.18, 0.0)),
        dtype=dtype,
    )
    covariances_np = np.asarray(
        (
            np.diag((0.05**2, 0.08**2, 0.04**2)),
            np.diag((0.07**2, 0.03**2, 0.06**2)),
            np.diag((0.04**2, 0.05**2, 0.09**2)),
        ),
        dtype=dtype,
    )
    extinction_np = np.asarray((1.0, 0.7, 0.4), dtype=dtype)
    index = build_spatial_index(
        centers_np, covariances_np, bin_size=0.08, max_bins_per_gaussian=256
    )
    device = torch.device("cpu")
    torch_index = index.to(device)
    samples = torch.tensor(
        (
            (0.0, 0.0, 0.0),
            (0.10, 0.0, 0.0),
            (0.22, -0.03, 0.02),
            (-0.15, 0.18, 0.0),
            (10.0, 10.0, 10.0),
            tuple(index.origin.tolist()),
        ),
        dtype=torch.float32,
    )
    centers = torch.tensor(centers_np, requires_grad=True)
    precisions = torch.tensor(
        np.linalg.inv(covariances_np), dtype=torch.float32, requires_grad=True
    )
    extinction = torch.tensor(extinction_np, requires_grad=True)
    indexed = evaluate_field(
        samples, centers, precisions, extinction, torch_index
    )
    brute = brute_field(samples, centers, precisions, extinction)
    if not torch.allclose(indexed, brute, atol=1e-6, rtol=1e-5):
        raise AssertionError(f"indexed/brute mismatch: {indexed} != {brute}")
    if indexed[-2] != 0.0:
        raise AssertionError("out-of-bounds sample must return zero")
    indexed.sum().backward()
    for name, parameter in (
        ("center", centers),
        ("precision", precisions),
        ("extinction", extinction),
    ):
        if parameter.grad is None or not torch.isfinite(parameter.grad).all():
            raise AssertionError(f"{name} gradient is not finite")
    try:
        build_spatial_index(
            centers_np,
            covariances_np * 100.0,
            bin_size=0.01,
            max_bins_per_gaussian=8,
        )
    except ValueError:
        guard_passed = True
    else:
        raise AssertionError("oversized-support guard did not fire")
    return {
        "status": "passed",
        "indexed_brute_max_abs_error": float(
            (indexed - brute).abs().max().detach()
        ),
        "empty_bin_zero": True,
        "finite_gradients": True,
        "boundary_sample_finite": bool(torch.isfinite(indexed[-1])),
        "oversized_support_guard": guard_passed,
        "cell_count": len(index.cell_offsets) - 1,
        "pair_count": len(index.gaussian_ids),
    }


def trainer_self_check() -> dict:
    device = torch.device("cpu")
    seed = 20_260_729
    random.seed(seed)
    torch.manual_seed(seed)
    generator = np.random.default_rng(seed)
    centers_np = np.asarray(
        ((-0.12, 0.0, 0.0), (0.14, 0.02, 0.0)), dtype=np.float32
    )
    covariance_np = np.asarray(
        (
            np.diag((0.07**2, 0.05**2, 0.06**2)),
            np.diag((0.06**2, 0.08**2, 0.05**2)),
        ),
        dtype=np.float32,
    )
    extinction_np = np.asarray((0.8, 0.6), dtype=np.float32)
    bounds = np.asarray(((-0.5,) * 3, (0.5,) * 3), dtype=np.float32)

    def target_field(points: np.ndarray) -> np.ndarray:
        points_t = torch.as_tensor(points)
        centers_t = torch.as_tensor(
            ((-0.08, 0.0, 0.0), (0.11, 0.04, 0.0)), dtype=torch.float32
        )
        covariance_t = torch.as_tensor(covariance_np)
        precision_t = torch.linalg.inv(covariance_t)
        extinction_t = torch.as_tensor((0.9, 0.7), dtype=torch.float32)
        return brute_field(
            points_t,
            centers_t,
            precision_t,
            extinction_t,
        ).numpy()

    model = FreeGaussians(
        centers_np,
        covariance_np,
        extinction_np,
        bounds,
        min_scale=0.01,
        max_scale=0.2,
    ).to(device)
    optimizer = make_optimizer(model, geometry_lr=1e-3, extinction_lr=1e-3)
    reference_mass = float(model.mass().sum().detach())
    first_samples_np = generator.uniform(-0.25, 0.25, size=(128, 3)).astype(
        np.float32
    )
    first = density_step(
        model,
        optimizer,
        torch.as_tensor(first_samples_np),
        torch.as_tensor(target_field(first_samples_np)),
        reference_mass,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    hashes = {"source": "synthetic", "roi": "synthetic"}
    index_settings = {
        "bin_size": 0.1,
        "support_sigma": 3.0,
        "max_bins_per_gaussian": 256,
    }
    with tempfile.TemporaryDirectory() as directory:
        checkpoint = Path(directory) / "checkpoint.pt"
        save_checkpoint(
            checkpoint,
            model,
            optimizer,
            generator,
            phase="self_check",
            round_index=0,
            step=1,
            densification_state={"rounds": 0},
            hashes=hashes,
            index_settings=index_settings,
        )
        second_samples_np = generator.uniform(
            -0.25, 0.25, size=(128, 3)
        ).astype(np.float32)
        second_target = target_field(second_samples_np)
        continuous = density_step(
            model,
            optimizer,
            torch.as_tensor(second_samples_np),
            torch.as_tensor(second_target),
            reference_mass,
            bin_size=0.1,
            support_sigma=3.0,
            max_bins_per_gaussian=256,
        )
        continuous_state = model.checkpoint_state()

        resumed_model, resumed_optimizer, resumed_generator, payload = (
            load_checkpoint(
                checkpoint,
                device,
                hashes,
                geometry_lr=1e-3,
                extinction_lr=1e-3,
            )
        )
        resumed_samples_np = resumed_generator.uniform(
            -0.25, 0.25, size=(128, 3)
        ).astype(np.float32)
        if not np.array_equal(second_samples_np, resumed_samples_np):
            raise AssertionError("resumed NumPy sample stream changed")
        resumed = density_step(
            resumed_model,
            resumed_optimizer,
            torch.as_tensor(resumed_samples_np),
            torch.as_tensor(second_target),
            reference_mass,
            bin_size=0.1,
            support_sigma=3.0,
            max_bins_per_gaussian=256,
        )
        resumed_state = resumed_model.checkpoint_state()
        maximum_parameter_error = max(
            float((continuous_state[name] - resumed_state[name]).abs().max())
            for name in continuous_state
        )
        if maximum_parameter_error > 1e-8:
            raise AssertionError("checkpoint resume changed the next step")
        if payload["step"] != 1 or payload["point_count"] != 2:
            raise AssertionError("checkpoint progress metadata changed")
        exported = Path(directory) / "candidate.npz"
        save_model_npz(resumed_model, exported)
        with np.load(exported) as exported_data:
            if len(exported_data["center_m"]) != 2:
                raise AssertionError(
                    "candidate NPZ export changed the point count"
                )
        initializer_path = Path(directory) / "initializer.npz"
        roi_path = Path(directory) / "roi.npy"
        hybrid_path = Path(directory) / "hybrid.npz"
        np.savez_compressed(
            initializer_path,
            center_m=centers_np,
            covariance_m2=covariance_np,
            sigma_t_per_m=extinction_np,
        )
        np.save(roi_path, np.asarray((1,), dtype=np.int64))
        hybrid_report = save_hybrid_npz(
            initializer_path,
            roi_path,
            exported,
            hybrid_path,
        )
        if hybrid_report["combined_count"] != 3:
            raise AssertionError("hybrid export changed the expected count")

    error_positions = np.asarray(
        (
            (-0.35, -0.25, 0.0),
            (0.35, 0.25, 0.0),
            (0.0, 0.35, 0.0),
            (0.0, -0.35, 0.0),
        ),
        dtype=np.float32,
    )
    errors = np.asarray((1.0, 0.8, 0.6, 0.4), dtype=np.float32)
    new_covariance = np.repeat(
        (np.eye(3, dtype=np.float32) * 0.04**2)[None],
        len(errors),
        axis=0,
    )
    densified, densification = densify_prune(
        resumed_model,
        error_positions,
        errors,
        residual_extinction=np.full(len(errors), 0.2, np.float32),
        new_covariances=new_covariance,
        target_count=3,
        max_new=1,
        min_distance=0.05,
    )
    _, covariance, _, _, extinction = densified.kernels()
    minimum_eigenvalue = float(
        torch.linalg.eigvalsh(covariance.detach()).min()
    )
    if (
        len(densified.center_m) != 3
        or minimum_eigenvalue <= 0.0
        or not bool(torch.all(extinction > 0.0))
    ):
        raise AssertionError("densification produced invalid kernels")
    grid_coordinates = np.indices((17, 15, 13), dtype=np.float32)
    delta = grid_coordinates - np.asarray((8.0, 7.0, 6.0))[:, None, None, None]
    synthetic_grid = np.exp(
        -0.5
        * (
            (delta[0] / 3.0) ** 2
            + (delta[1] / 2.0) ** 2
            + (delta[2] / 1.0) ** 2
        )
    ).astype(np.float32)
    source = DensityGrid(
        synthetic_grid, longest_size_m=1.0, density_scale_per_cm=0.04
    )
    sampling_rng = np.random.default_rng(seed)
    sampled_points, sampled_target = source.sample_training(
        sampling_rng, active_count=24, edge_count=24, empty_count=16
    )
    roundtrip_error = float(
        np.max(
            np.abs(
                source.grid_to_world(source.world_to_grid(sampled_points))
                - sampled_points
            )
        )
    )
    covariance_probes = np.concatenate(
        (
            source.grid_to_world(
                np.asarray(((8.0, 7.0, 6.0),), dtype=np.float32)
            ),
            sampled_points[:7],
        )
    )
    local_covariance = source.local_covariances(
        covariance_probes, min_scale=0.02, max_scale=0.15
    )
    local_eigenvalues = np.linalg.eigvalsh(local_covariance)
    if (
        roundtrip_error > 1e-6
        or not np.isfinite(sampled_target).all()
        or np.any(sampled_target < 0.0)
        or np.any(local_eigenvalues <= 0.0)
        or np.allclose(
            sampled_points / source.voxel_m,
            np.round(sampled_points / source.voxel_m),
        )
    ):
        raise AssertionError("continuous source-grid sampling failed")
    seed_covariance = source.local_covariances(
        sampled_points[:48], min_scale=0.02, max_scale=0.15
    )
    seed_points, _, seed_extinction = select_weighted_seeds(
        sampled_points[:48],
        np.maximum(sampled_target[:48], 1e-6),
        seed_covariance,
        count=8,
        min_distance=0.02,
        generator=sampling_rng,
    )
    if len(seed_points) != 8 or np.any(seed_extinction <= 0.0):
        raise AssertionError("weighted seed selection failed")
    ray_origins = torch.tensor(((0.0, 0.0, -1.0),), dtype=torch.float32)
    ray_directions = torch.tensor(((0.0, 0.0, 1.0),), dtype=torch.float32)
    ray_tau = densified.optical_depth(ray_origins, ray_directions, chunk=1)
    if not bool(torch.isfinite(ray_tau).all()) or bool(torch.any(ray_tau < 0.0)):
        raise AssertionError("analytic ray integral failed")
    equal_ray_losses = ray_losses(
        ray_tau.repeat(25), ray_tau.detach().repeat(25), patch_size=5
    )
    if any(float(value.detach()) != 0.0 for value in equal_ray_losses.values()):
        raise AssertionError("equal ray loss must be zero")
    progress = recovery_progress(
        {"tau_mae": 1.02, "edge_l1": 0.99},
        {"tau_mae": 1.03, "edge_l1": 0.98},
        {"tau_mae": 1.0, "edge_l1": 1.0},
        {"tau_mae": 1.0, "edge_l1": 1.0},
        {
            "global": {"tau_mae": 1.0, "edge_l1": 1.0},
            "roi": {"tau_mae": 1.0, "edge_l1": 1.0},
        },
    )
    if not progress["joint_tau_regression"]:
        raise AssertionError("P2b joint tau regression Gate failed")
    return {
        "status": "passed",
        "first_loss": first["loss"],
        "continuous_second_loss": continuous["loss"],
        "resumed_second_loss": resumed["loss"],
        "resume_parameter_max_abs_error": maximum_parameter_error,
        "next_sample_stream_exact": True,
        "checkpoint_progress_restored": True,
        "hybrid_export_count": hybrid_report["combined_count"],
        "densification": densification,
        "minimum_covariance_eigenvalue": minimum_eigenvalue,
        "positive_extinction": True,
        "source_sampling": {
            "count": len(sampled_points),
            "world_grid_roundtrip_max_abs_error": roundtrip_error,
            "target_min_max": [
                float(sampled_target.min()),
                float(sampled_target.max()),
            ],
            "continuous_in_cell": True,
            "local_covariance_min_eigenvalue": float(
                local_eigenvalues.min()
            ),
            "local_covariance_max_anisotropy": float(
                np.max(local_eigenvalues[:, -1] / local_eigenvalues[:, 0])
            ),
            "weighted_seed_count": len(seed_points),
        },
        "analytic_ray_tau": float(ray_tau.detach()),
        "equal_ray_losses_zero": True,
        "p2b_joint_tau_regression_gate": True,
    }


def real_smoke(
    source_grid: Path,
    initializer: Path,
    count: int,
    sample_count: int,
    device: torch.device,
    seed: int,
) -> dict:
    started = time.perf_counter()
    source = DensityGrid(
        source_grid, longest_size_m=10.0, density_scale_per_cm=0.04
    )
    data = np.load(initializer)
    total = len(data["center_m"])
    if count <= 0 or count > total or sample_count < 4:
        raise ValueError("real smoke count or sample count is invalid")
    selected = (
        np.arange(total)
        if count == total
        else np.linspace(0, total - 1, count, dtype=np.int64)
    )
    model = FreeGaussians(
        np.asarray(data["center_m"][selected], dtype=np.float32),
        np.asarray(data["covariance_m2"][selected], dtype=np.float32),
        np.maximum(
            np.asarray(data["sigma_t_per_m"][selected], dtype=np.float32),
            1e-8,
        ),
        source.bounds_world().astype(np.float32),
        min_scale=source.voxel_m * 0.25,
        max_scale=0.15,
    ).to(device)
    optimizer = make_optimizer(
        model, geometry_lr=5e-4, extinction_lr=5e-4
    )
    generator = np.random.default_rng(seed)
    empty = sample_count // 4
    edge = sample_count // 4
    points, target = source.sample_training(
        generator,
        active_count=sample_count - edge - empty,
        edge_count=edge,
        empty_count=empty,
    )
    reference_mass = float(model.mass().sum().detach())
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
    step_started = time.perf_counter()
    report = density_step(
        model,
        optimizer,
        torch.as_tensor(points, dtype=torch.float32, device=device),
        torch.as_tensor(target, dtype=torch.float32, device=device),
        reference_mass,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    step_seconds = time.perf_counter() - step_started
    report.pop("error")
    report.pop("prediction")
    with torch.no_grad():
        _, covariance, _, _, extinction = model.kernels()
    return {
        "status": "passed",
        "source_grid": str(source_grid.resolve()),
        "source_grid_sha256": _sha256(source_grid),
        "initializer": str(initializer.resolve()),
        "initializer_sha256": _sha256(initializer),
        "gaussian_count": count,
        "sample_count": sample_count,
        "device": str(device),
        "gpu": (
            torch.cuda.get_device_name(device) if device.type == "cuda" else None
        ),
        "step": report,
        "step_seconds": step_seconds,
        "total_seconds": time.perf_counter() - started,
        "gpu_peak_allocated_mib": (
            torch.cuda.max_memory_allocated(device) / 2**20
            if device.type == "cuda"
            else 0.0
        ),
        "finite_parameters": all(
            bool(torch.isfinite(parameter).all())
            for parameter in model.parameters()
        ),
        "minimum_covariance_eigenvalue": float(
            np.linalg.eigvalsh(covariance.detach().cpu().numpy()).min()
        ),
        "minimum_extinction": float(extinction.min()),
        "recommended_rebuild_interval": 1,
        "reason": (
            "First implementation rebuilds every step; measured motion is "
            "recorded before introducing padded multi-step reuse."
        ),
    }


def _ray_hits_mask(
    origins: np.ndarray,
    directions: np.ndarray,
    source: DensityGrid,
    block_mask: np.ndarray,
    block_size: int,
    steps: int = 96,
    chunk: int = 4096,
) -> np.ndarray:
    bounds = source.bounds_world()
    result = np.zeros(len(origins), dtype=bool)
    fraction = (np.arange(steps, dtype=np.float32) + 0.5) / steps
    for start in range(0, len(origins), chunk):
        stop = min(start + chunk, len(origins))
        ray_origin = origins[start:stop]
        ray_direction = directions[start:stop]
        inverse = np.where(
            np.abs(ray_direction) > 1e-8, 1.0 / ray_direction, 1e8
        )
        t0 = (bounds[0] - ray_origin) * inverse
        t1 = (bounds[1] - ray_origin) * inverse
        enter = np.maximum(np.minimum(t0, t1).max(axis=1), 0.0)
        leave = np.maximum(t0, t1).min(axis=1)
        valid = leave > enter
        distance = (
            enter[:, None]
            + np.maximum(leave - enter, 0.0)[:, None] * fraction[None]
        )
        points = (
            ray_origin[:, None]
            + ray_direction[:, None] * distance[:, :, None]
        )
        coordinates = source.world_to_grid(points.reshape(-1, 3))
        blocks = np.floor(
            (coordinates + 1e-4) / block_size
        ).astype(np.int64)
        block_shape = np.asarray(block_mask.shape)
        inside = np.all(
            (blocks >= 0) & (blocks < block_shape), axis=1
        )
        hit = np.zeros(len(blocks), dtype=bool)
        valid_blocks = blocks[inside]
        hit[inside] = block_mask[
            valid_blocks[:, 0], valid_blocks[:, 1], valid_blocks[:, 2]
        ]
        result[start:stop] = valid & hit.reshape(stop - start, steps).any(axis=1)
    return result


def prepare_roi(
    source_grid: Path,
    initializer: Path,
    dataset: Path,
    output: Path,
    count: int,
    block_size: int,
    seed: int,
) -> dict:
    from recover_contracted_50k import _patch_pool, load_rays

    source = DensityGrid(
        source_grid, longest_size_m=10.0, density_scale_per_cm=0.04
    )
    data = np.load(initializer)
    centers = np.asarray(data["center_m"], dtype=np.float32)
    covariances = np.asarray(data["covariance_m2"], dtype=np.float32)
    if count <= 0 or count >= len(centers) or block_size <= 0:
        raise ValueError("ROI count and block size are invalid")
    coordinates = source.world_to_grid(centers)
    cells = np.floor((coordinates + 1e-4) / block_size).astype(np.int32)
    unique_cells = np.unique(cells, axis=0)
    block_shape = tuple(
        int(math.ceil(size / block_size)) for size in source.shape
    )
    if np.any(cells < 0) or np.any(cells >= np.asarray(block_shape)):
        raise ValueError("G2 center maps outside the source block grid")

    origins, directions, optical_depth = load_rays(dataset)
    anchor_view = 1
    anchor_origin = origins[anchor_view, optical_depth.shape[1] // 2, optical_depth.shape[2] // 2]
    anchor_direction = directions[
        anchor_view, optical_depth.shape[1] // 2, optical_depth.shape[2] // 2
    ]
    bounds = source.bounds_world()
    inverse = np.where(np.abs(anchor_direction) > 1e-8, 1.0 / anchor_direction, 1e8)
    t0 = (bounds[0] - anchor_origin) * inverse
    t1 = (bounds[1] - anchor_origin) * inverse
    enter = max(float(np.minimum(t0, t1).max()), 0.0)
    leave = float(np.maximum(t0, t1).min())
    if leave <= enter:
        raise RuntimeError("anchor camera ray misses the source bounds")
    distances = np.linspace(enter, leave, 2048, dtype=np.float32)
    anchor_points = anchor_origin + distances[:, None] * anchor_direction
    anchor_density = source.sample_world(anchor_points)
    delta_m = (leave - enter) / len(distances)
    cumulative_tau = np.cumsum(anchor_density * delta_m)
    threshold = min(0.3, float(cumulative_tau[-1]) * 0.25)
    anchor_sample = int(np.searchsorted(cumulative_tau, threshold))
    anchor = anchor_points[min(anchor_sample, len(anchor_points) - 1)]

    lookup: dict[tuple[int, int, int], list[int]] = {}
    for index, cell_array in enumerate(cells):
        lookup.setdefault(tuple(cell_array), []).append(index)
    start_index = int(
        np.argmin(np.sum((centers - anchor[None]) ** 2, axis=1))
    )
    start_cell = tuple(cells[start_index])
    queued = {start_cell}
    selected: list[int] = []
    queue = [
        (
            float(np.sum((centers[start_index] - anchor) ** 2)),
            start_cell,
        )
    ]
    neighbor_offsets = [
        (x, y, z)
        for x in (-1, 0, 1)
        for y in (-1, 0, 1)
        for z in (-1, 0, 1)
        if (x, y, z) != (0, 0, 0)
    ]
    while queue and len(selected) < count:
        _, cell = heapq.heappop(queue)
        members = lookup[cell]
        remaining = count - len(selected)
        if len(members) > remaining:
            member_array = np.asarray(members, dtype=np.int64)
            distance = np.sum(
                (centers[member_array] - anchor[None]) ** 2, axis=1
            )
            members = member_array[np.argsort(distance)[:remaining]].tolist()
        selected.extend(members)
        for offset in neighbor_offsets:
            neighbor = tuple(cell[axis] + offset[axis] for axis in range(3))
            if neighbor in lookup and neighbor not in queued:
                queued.add(neighbor)
                neighbor_indices = np.asarray(
                    lookup[neighbor], dtype=np.int64
                )
                priority = float(
                    np.min(
                        np.sum(
                            (centers[neighbor_indices] - anchor[None]) ** 2,
                            axis=1,
                        )
                    )
                )
                heapq.heappush(queue, (priority, neighbor))
    if len(selected) != count:
        raise RuntimeError(
            f"connected ROI stopped at {len(selected)} of {count} cells"
        )
    roi_indices = np.sort(np.asarray(selected, dtype=np.int64))
    roi_core_mask = np.zeros(block_shape, dtype=bool)
    roi_cells = cells[roi_indices]
    roi_core_mask[
        roi_cells[:, 0], roi_cells[:, 1], roi_cells[:, 2]
    ] = True
    maximum_support_m = float(
        3.0
        * np.sqrt(
            np.diagonal(covariances, axis1=1, axis2=2)
        ).max()
    )
    halo_blocks = max(
        1,
        int(
            math.ceil(
                maximum_support_m / (block_size * source.voxel_m)
            )
        ),
    )
    mask_tensor = torch.as_tensor(
        roi_core_mask[None, None], dtype=torch.float32
    )
    roi_halo_mask = (
        F.max_pool3d(
            mask_tensor,
            kernel_size=halo_blocks * 2 + 1,
            stride=1,
            padding=halo_blocks,
        )[0, 0]
        > 0.0
    ).numpy()

    heldout_views = np.arange(1, len(origins), 4)
    patch_centers, patch_weights = _patch_pool(
        optical_depth, heldout_views, margin=2
    )
    patch_origins = origins[
        patch_centers[:, 0], patch_centers[:, 1], patch_centers[:, 2]
    ]
    patch_directions = directions[
        patch_centers[:, 0], patch_centers[:, 1], patch_centers[:, 2]
    ]
    hits = _ray_hits_mask(
        patch_origins,
        patch_directions,
        source,
        roi_core_mask,
        block_size,
    )
    hit_centers = patch_centers[hits]
    hit_weights = patch_weights[hits]
    if len(hit_centers) < 8:
        raise RuntimeError(
            f"only {len(hit_centers)} held-out patches cross the ROI"
        )
    generator = np.random.default_rng(seed)
    heldout_count = min(64, len(hit_centers))
    heldout_indices = generator.choice(
        len(hit_centers),
        size=heldout_count,
        replace=False,
        p=hit_weights / hit_weights.sum(),
    )
    roi_heldout = hit_centers[heldout_indices]
    roi_heldout = roi_heldout[
        np.lexsort((roi_heldout[:, 2], roi_heldout[:, 1], roi_heldout[:, 0]))
    ]
    global_generator = np.random.default_rng(20_260_727)
    global_count = 1000 // 25
    global_heldout = patch_centers[
        global_generator.choice(
            len(patch_centers),
            size=global_count,
            replace=False,
            p=patch_weights,
        )
    ]
    global_heldout = global_heldout[
        np.lexsort(
            (
                global_heldout[:, 2],
                global_heldout[:, 1],
                global_heldout[:, 0],
            )
        )
    ]

    output.mkdir(parents=True, exist_ok=True)
    np.save(output / "roi_indices.npy", roi_indices)
    np.save(output / "roi_core_mask.npy", roi_core_mask)
    np.save(output / "roi_halo_mask.npy", roi_halo_mask)
    np.save(output / "roi_heldout_patch_indices.npy", roi_heldout)
    np.save(output / "global_heldout_patch_indices.npy", global_heldout)
    report = {
        "status": "prepared",
        "source_grid": str(source_grid.resolve()),
        "initializer": str(initializer.resolve()),
        "dataset": str(dataset.resolve()),
        "source_grid_sha256": _sha256(source_grid),
        "initializer_sha256": _sha256(initializer),
        "roi_count": len(roi_indices),
        "frozen_count": len(centers) - len(roi_indices),
        "block_size": block_size,
        "block_shape": block_shape,
        "occupied_b8_cell_count": len(unique_cells),
        "duplicate_center_cell_count": len(centers) - len(unique_cells),
        "roi_core_cell_count": int(roi_core_mask.sum()),
        "roi_halo_cell_count": int(roi_halo_mask.sum()),
        "halo_blocks": halo_blocks,
        "maximum_g2_support_m": maximum_support_m,
        "anchor_view": anchor_view,
        "anchor_world_m": anchor.tolist(),
        "anchor_tau_threshold": threshold,
        "heldout_views": heldout_views.tolist(),
        "heldout_crossing_patch_pool": int(len(hit_centers)),
        "roi_heldout_patch_count": len(roi_heldout),
        "global_heldout_patch_count": len(global_heldout),
        "roi_indices_sha256": _sha256(output / "roi_indices.npy"),
        "roi_core_mask_sha256": _sha256(output / "roi_core_mask.npy"),
        "roi_halo_mask_sha256": _sha256(output / "roi_halo_mask.npy"),
        "roi_heldout_patch_indices_sha256": _sha256(
            output / "roi_heldout_patch_indices.npy"
        ),
        "global_heldout_patch_indices_sha256": _sha256(
            output / "global_heldout_patch_indices.npy"
        ),
        "connected_26_neighbor": True,
        "ue_deployed": False,
    }
    _write_json(output / "roi.json", report)
    return report


def p2_dry_run(
    source_grid: Path,
    initializer: Path,
    dataset: Path,
    root: Path,
    candidate_count: int,
    sample_count: int,
    device: torch.device,
    seed: int,
) -> dict:
    from recover_contracted_50k import _gather_patches, load_rays

    started = time.perf_counter()
    roi_report = json.loads(
        (root / "roi.json").read_text(encoding="utf-8")
    )
    roi_indices = np.load(root / "roi_indices.npy")
    roi_core_mask = np.load(root / "roi_core_mask.npy")
    roi_halo_mask = np.load(root / "roi_halo_mask.npy")
    roi_heldout = np.load(root / "roi_heldout_patch_indices.npy")
    if (
        _sha256(initializer) != roi_report["initializer_sha256"]
        or _sha256(root / "roi_indices.npy")
        != roi_report["roi_indices_sha256"]
        or _sha256(root / "roi_core_mask.npy")
        != roi_report["roi_core_mask_sha256"]
        or _sha256(root / "roi_halo_mask.npy")
        != roi_report["roi_halo_mask_sha256"]
    ):
        raise ValueError("P2 ROI inputs no longer match their hashes")
    data = np.load(initializer)
    centers = np.asarray(data["center_m"], dtype=np.float32)
    covariance = np.asarray(data["covariance_m2"], dtype=np.float32)
    extinction = np.maximum(
        np.asarray(data["sigma_t_per_m"], dtype=np.float32), 1e-8
    )
    outside = np.ones(len(centers), dtype=bool)
    outside[roi_indices] = False
    if int(outside.sum()) != roi_report["frozen_count"]:
        raise ValueError("P2 frozen point count changed")
    source = DensityGrid(
        source_grid, longest_size_m=10.0, density_scale_per_cm=0.04
    )
    if device.type == "cuda":
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats(device)
    frozen = FrozenField.from_arrays(
        centers[outside],
        covariance[outside],
        extinction[outside],
        device,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    removed = FrozenField.from_arrays(
        centers[roi_indices],
        covariance[roi_indices],
        extinction[roi_indices],
        device,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    full = FrozenField.from_arrays(
        centers,
        covariance,
        extinction,
        device,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    generator = np.random.default_rng(seed)
    parity_points, _ = source.sample_training(
        generator,
        active_count=64,
        edge_count=32,
        empty_count=32,
        block_mask=roi_halo_mask,
        block_size=roi_report["block_size"],
    )
    parity_samples = torch.as_tensor(
        parity_points, dtype=torch.float32, device=device
    )
    with torch.no_grad():
        split_prediction = frozen.evaluate(
            parity_samples, 3.0
        ) + removed.evaluate(parity_samples, 3.0)
        full_prediction = full.evaluate(parity_samples, 3.0)
    split_max_error = float(
        (split_prediction - full_prediction).abs().max()
    )
    if split_max_error > 1e-5:
        raise AssertionError(
            f"frozen/ROI split changed the G2 field by {split_max_error}"
        )
    del full
    if device.type == "cuda":
        torch.cuda.empty_cache()

    pool_count = max(candidate_count * 8, 2048)
    pool_points, pool_target = source.sample_training(
        generator,
        active_count=pool_count // 2,
        edge_count=pool_count // 2,
        empty_count=0,
        block_mask=roi_core_mask,
        block_size=roi_report["block_size"],
    )
    with torch.no_grad():
        pool_frozen = frozen.evaluate(
            torch.as_tensor(
                pool_points, dtype=torch.float32, device=device
            ),
            3.0,
        ).cpu().numpy()
    residual = np.maximum(pool_target - pool_frozen, 1e-6)
    pool_covariance = source.local_covariances(
        pool_points,
        min_scale=source.voxel_m * 0.5,
        max_scale=0.06,
    )
    seed_centers, seed_covariance, seed_extinction = select_weighted_seeds(
        pool_points,
        residual,
        pool_covariance,
        count=candidate_count,
        min_distance=source.voxel_m * 1.25,
        generator=generator,
    )
    model = FreeGaussians(
        seed_centers,
        seed_covariance,
        seed_extinction,
        source.bounds_world().astype(np.float32),
        min_scale=source.voxel_m * 0.25,
        max_scale=0.065,
    ).to(device)
    optimizer = make_optimizer(
        model, geometry_lr=5e-4, extinction_lr=5e-4
    )
    removed_mass = float(
        np.sum(
            extinction[roi_indices]
            * GAUSSIAN_VOLUME
            * np.sqrt(np.linalg.det(covariance[roi_indices]))
        )
    )
    empty = sample_count // 4
    edge = sample_count // 4
    samples_np, target_np = source.sample_training(
        generator,
        active_count=sample_count - edge - empty,
        edge_count=edge,
        empty_count=empty,
        block_mask=roi_halo_mask,
        block_size=roi_report["block_size"],
    )
    step = density_step(
        model,
        optimizer,
        torch.as_tensor(samples_np, dtype=torch.float32, device=device),
        torch.as_tensor(target_np, dtype=torch.float32, device=device),
        removed_mass,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
        frozen=frozen,
        allowed_region=(
            source,
            roi_halo_mask,
            roi_report["block_size"],
        ),
    )
    step.pop("error")
    step.pop("prediction")
    hashes = {
        "source": roi_report["source_grid_sha256"],
        "g2": roi_report["initializer_sha256"],
        "roi": roi_report["roi_indices_sha256"],
        "roi_core": roi_report["roi_core_mask_sha256"],
        "roi_halo": roi_report["roi_halo_mask_sha256"],
        "heldout": roi_report["roi_heldout_patch_indices_sha256"],
    }
    checkpoint = root / "dry_run" / "checkpoint.pt"
    save_checkpoint(
        checkpoint,
        model,
        optimizer,
        generator,
        phase="p2_dry_run",
        round_index=0,
        step=1,
        densification_state={"target_count": candidate_count},
        hashes=hashes,
        index_settings={
            "bin_size": 0.1,
            "support_sigma": 3.0,
            "rebuild_interval": 1,
        },
    )
    loaded_model, _, _, payload = load_checkpoint(
        checkpoint,
        device,
        hashes,
        geometry_lr=5e-4,
        extinction_lr=5e-4,
    )
    origins, directions, optical_depth = load_rays(dataset)
    ray_origins, ray_directions, ray_target = _gather_patches(
        origins,
        directions,
        optical_depth,
        roi_heldout[:1],
        radius=2,
    )
    ray_origins_t = torch.as_tensor(
        ray_origins, dtype=torch.float32, device=device
    )
    ray_directions_t = torch.as_tensor(
        ray_directions, dtype=torch.float32, device=device
    )
    with torch.no_grad():
        ray_prediction = frozen.optical_depth(
            ray_origins_t, ray_directions_t
        ) + loaded_model.optical_depth(
            ray_origins_t, ray_directions_t
        )
    ray_target_t = torch.as_tensor(
        ray_target, dtype=torch.float32, device=device
    )
    ray_metric = ray_losses(
        ray_prediction, ray_target_t, patch_size=5
    )
    if (
        payload["point_count"] != candidate_count
        or not bool(torch.isfinite(ray_prediction).all())
        or bool(torch.any(ray_prediction < 0.0))
    ):
        raise AssertionError("P2 dry-run checkpoint or hybrid rays failed")
    report = {
        "status": "passed",
        "candidate_count": candidate_count,
        "frozen_count": int(outside.sum()),
        "combined_count": int(outside.sum()) + candidate_count,
        "sample_count": sample_count,
        "split_full_field_max_abs_error": split_max_error,
        "density_step": step,
        "checkpoint_point_count": payload["point_count"],
        "hybrid_ray_tau_min_max": [
            float(ray_prediction.min()),
            float(ray_prediction.max()),
        ],
        "hybrid_ray_losses": {
            name: float(value) for name, value in ray_metric.items()
        },
        "gpu_peak_allocated_mib": (
            torch.cuda.max_memory_allocated(device) / 2**20
            if device.type == "cuda"
            else 0.0
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "ue_deployed": False,
    }
    _write_json(root / "dry_run" / "report.json", report)
    return report


def train_p2(
    source_grid: Path,
    initializer: Path,
    dataset: Path,
    root: Path,
    device: torch.device,
    seed: int,
    field_steps: int,
    ray_steps_count: int,
    sample_count: int,
    error_sample_count: int,
    resume: bool,
    *,
    input_root: Path | None = None,
    schedule: tuple[int, ...] = (
        10_000,
        20_000,
        30_000,
        40_000,
        50_000,
    ),
    warm_start: Path | None = None,
    parent_metrics_path: Path | None = None,
    stop_on_joint_tau_regression: bool = False,
) -> dict:
    from recover_contracted_50k import (
        _gather_patches,
        _patch_pool,
        load_rays,
    )
    from run_degrid_overnight import lattice_order

    input_root = input_root or root
    if (warm_start is None) != (parent_metrics_path is None):
        raise ValueError("warm start and parent metrics must be provided together")
    if not schedule or any(
        current <= 0 or (index and current <= schedule[index - 1])
        for index, current in enumerate(schedule)
    ):
        raise ValueError("training schedule must be positive and increasing")
    roi_report = json.loads(
        (input_root / "roi.json").read_text(encoding="utf-8")
    )
    roi_indices = np.load(input_root / "roi_indices.npy")
    core_mask = np.load(input_root / "roi_core_mask.npy")
    halo_mask = np.load(input_root / "roi_halo_mask.npy")
    roi_heldout = np.load(input_root / "roi_heldout_patch_indices.npy")
    global_heldout = np.load(input_root / "global_heldout_patch_indices.npy")
    hashes = {
        "source": roi_report["source_grid_sha256"],
        "g2": roi_report["initializer_sha256"],
        "roi": roi_report["roi_indices_sha256"],
        "roi_core": roi_report["roi_core_mask_sha256"],
        "roi_halo": roi_report["roi_halo_mask_sha256"],
        "heldout": roi_report["roi_heldout_patch_indices_sha256"],
        "global_heldout": roi_report[
            "global_heldout_patch_indices_sha256"
        ],
    }
    if warm_start is not None:
        hashes["warm_start"] = _sha256(warm_start)
    if parent_metrics_path is not None:
        hashes["parent_metrics"] = _sha256(parent_metrics_path)
    if (
        _sha256(initializer) != hashes["g2"]
        or _sha256(input_root / "roi_indices.npy") != hashes["roi"]
        or _sha256(input_root / "global_heldout_patch_indices.npy")
        != hashes["global_heldout"]
    ):
        raise ValueError("P2 inputs no longer match their frozen hashes")
    data = np.load(initializer)
    all_centers = np.asarray(data["center_m"], dtype=np.float32)
    all_covariance = np.asarray(
        data["covariance_m2"], dtype=np.float32
    )
    all_extinction = np.maximum(
        np.asarray(data["sigma_t_per_m"], dtype=np.float32), 1e-8
    )
    outside = np.ones(len(all_centers), dtype=bool)
    outside[roi_indices] = False
    source = DensityGrid(
        source_grid, longest_size_m=10.0, density_scale_per_cm=0.04
    )
    frozen = FrozenField.from_arrays(
        all_centers[outside],
        all_covariance[outside],
        all_extinction[outside],
        device,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    removed = FrozenField.from_arrays(
        all_centers[roi_indices],
        all_covariance[roi_indices],
        all_extinction[roi_indices],
        device,
        bin_size=0.1,
        support_sigma=3.0,
        max_bins_per_gaussian=256,
    )
    reference_mass = float(
        np.sum(
            all_extinction[roi_indices]
            * GAUSSIAN_VOLUME
            * np.sqrt(np.linalg.det(all_covariance[roi_indices]))
        )
    )
    origins, directions, optical_depth = load_rays(dataset)
    heldout_views = np.arange(1, len(origins), 4)
    train_views = np.setdiff1d(np.arange(len(origins)), heldout_views)
    train_centers, train_weights = _patch_pool(
        optical_depth, train_views, margin=2
    )
    baseline_path = input_root / "baseline_metrics.json"
    if baseline_path.exists():
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    else:
        baseline = {
            "global": evaluate_hybrid(
                frozen,
                removed,
                origins,
                directions,
                optical_depth,
                global_heldout,
                device,
            ),
            "roi": evaluate_hybrid(
                frozen,
                removed,
                origins,
                directions,
                optical_depth,
                roi_heldout,
                device,
            ),
        }
        _write_json(baseline_path, baseline)

    parent_metrics = (
        json.loads(parent_metrics_path.read_text(encoding="utf-8"))
        if parent_metrics_path is not None
        else None
    )
    checkpoint = root / "checkpoint.pt"
    summary_path = root / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status", "").startswith("complete"):
            return summary
        rounds = summary.get("rounds", [])
        best = summary.get("best")
    else:
        rounds = []
        best = None
    if resume:
        if not checkpoint.exists():
            raise FileNotFoundError("P2 resume checkpoint does not exist")
        model, optimizer, generator, payload = load_checkpoint(
            checkpoint,
            device,
            hashes,
            geometry_lr=5e-4,
            extinction_lr=5e-4,
        )
        round_index = int(payload["round"])
        phase = payload["phase"]
        phase_step = int(payload["step"])
    else:
        if checkpoint.exists():
            raise FileExistsError(
                "P2 checkpoint exists; use --resume or a new artifact root"
            )
        generator = np.random.default_rng(seed)
        if warm_start is None:
            model, initialization = initialize_p2_candidate(
                source,
                frozen,
                core_mask,
                roi_report["block_size"],
                schedule[0],
                reference_mass,
                generator,
                device,
            )
        else:
            with np.load(warm_start) as warm:
                if len(warm["center_m"]) != schedule[0]:
                    raise ValueError(
                        "warm-start count does not match schedule"
                    )
                model = FreeGaussians(
                    np.asarray(warm["center_m"], dtype=np.float32),
                    np.asarray(warm["covariance_m2"], dtype=np.float32),
                    np.maximum(
                        np.asarray(warm["sigma_t_per_m"], dtype=np.float32),
                        1e-8,
                    ),
                    source.bounds_world().astype(np.float32),
                    min_scale=source.voxel_m * 0.25,
                    max_scale=0.065,
                ).to(device)
            initialization = {
                "kind": "warm_start",
                "path": str(warm_start.resolve()),
                "sha256": hashes["warm_start"],
                "candidate_count": len(model.center_m),
            }
        optimizer = make_optimizer(
            model, geometry_lr=5e-4, extinction_lr=5e-4
        )
        round_index, phase, phase_step = 0, "field", 0
        _write_json(root / "initialization.json", initialization)
        save_checkpoint(
            checkpoint,
            model,
            optimizer,
            generator,
            phase=phase,
            round_index=round_index,
            step=phase_step,
            densification_state={"schedule": schedule},
            hashes=hashes,
            index_settings={
                "bin_size": 0.1,
                "support_sigma": 3.0,
                "rebuild_interval": 1,
            },
        )

    if best is None and parent_metrics is not None:
        parent_progress = recovery_progress(
            parent_metrics["global_metrics"],
            parent_metrics["roi_metrics"],
            parent_metrics["global_metrics"],
            parent_metrics["roi_metrics"],
            baseline,
        )
        best = {
            "kind": "warm_start",
            "path": str(warm_start.resolve()),
            "sha256": hashes["warm_start"],
            "score": parent_progress["score"],
            "global_metrics": parent_metrics["global_metrics"],
            "roi_metrics": parent_metrics["roi_metrics"],
        }

    started = time.perf_counter()
    allowed_region = (
        source,
        halo_mask,
        roi_report["block_size"],
    )
    while round_index < len(schedule):
        target_count = schedule[round_index]
        if len(model.center_m) != target_count:
            raise ValueError(
                f"round {round_index} expected {target_count} points, "
                f"found {len(model.center_m)}"
            )
        field_history = []
        ray_history = []
        if phase == "field":
            for step_index in range(phase_step, field_steps):
                empty = sample_count // 4
                edge = sample_count // 4
                samples_np, target_np = source.sample_training(
                    generator,
                    active_count=sample_count - edge - empty,
                    edge_count=edge,
                    empty_count=empty,
                    block_mask=halo_mask,
                    block_size=roi_report["block_size"],
                )
                row = density_step(
                    model,
                    optimizer,
                    torch.as_tensor(
                        samples_np, dtype=torch.float32, device=device
                    ),
                    torch.as_tensor(
                        target_np, dtype=torch.float32, device=device
                    ),
                    reference_mass,
                    bin_size=0.1,
                    support_sigma=3.0,
                    max_bins_per_gaussian=256,
                    frozen=frozen,
                    allowed_region=allowed_region,
                )
                row.pop("error")
                row.pop("prediction")
                row["step"] = step_index + 1
                field_history.append(row)
                if (step_index + 1) % 20 == 0:
                    print(
                        json.dumps(
                            {
                                "round": round_index,
                                "phase": "field",
                                **row,
                            }
                        ),
                        flush=True,
                    )
                    save_checkpoint(
                        checkpoint,
                        model,
                        optimizer,
                        generator,
                        phase="field",
                        round_index=round_index,
                        step=step_index + 1,
                        densification_state={"schedule": schedule},
                        hashes=hashes,
                        index_settings={
                            "bin_size": 0.1,
                            "support_sigma": 3.0,
                            "rebuild_interval": 1,
                        },
                    )
            phase, phase_step = "ray", 0
            save_checkpoint(
                checkpoint,
                model,
                optimizer,
                generator,
                phase=phase,
                round_index=round_index,
                step=0,
                densification_state={"schedule": schedule},
                hashes=hashes,
                index_settings={
                    "bin_size": 0.1,
                    "support_sigma": 3.0,
                    "rebuild_interval": 1,
                },
            )
        if phase == "ray":
            for step_index in range(phase_step, ray_steps_count):
                selected = train_centers[
                    generator.choice(
                        len(train_centers),
                        size=4,
                        replace=False,
                        p=train_weights,
                    )
                ]
                ray_origins, ray_directions, ray_target = _gather_patches(
                    origins,
                    directions,
                    optical_depth,
                    selected,
                    radius=2,
                )
                row = ray_step(
                    model,
                    optimizer,
                    frozen,
                    ray_origins,
                    ray_directions,
                    ray_target,
                    reference_mass,
                    allowed_region,
                )
                row["step"] = step_index + 1
                ray_history.append(row)
                print(
                    json.dumps(
                        {
                            "round": round_index,
                            "phase": "ray",
                            **row,
                        }
                    ),
                    flush=True,
                )
                if (step_index + 1) % 20 == 0:
                    save_checkpoint(
                        checkpoint,
                        model,
                        optimizer,
                        generator,
                        phase="ray",
                        round_index=round_index,
                        step=step_index + 1,
                        densification_state={"schedule": schedule},
                        hashes=hashes,
                        index_settings={
                            "bin_size": 0.1,
                            "support_sigma": 3.0,
                            "rebuild_interval": 1,
                        },
                    )
            phase, phase_step = "evaluation", 0
            save_checkpoint(
                checkpoint,
                model,
                optimizer,
                generator,
                phase=phase,
                round_index=round_index,
                step=0,
                densification_state={"schedule": schedule},
                hashes=hashes,
                index_settings={
                    "bin_size": 0.1,
                    "support_sigma": 3.0,
                    "rebuild_interval": 1,
                },
            )
        if phase == "evaluation":
            global_metrics = evaluate_hybrid(
                frozen,
                model,
                origins,
                directions,
                optical_depth,
                global_heldout,
                device,
            )
            roi_metrics = evaluate_hybrid(
                frozen,
                model,
                origins,
                directions,
                optical_depth,
                roi_heldout,
                device,
            )
            round_root = root / f"round_{round_index:02d}_{target_count:06d}"
            candidate_path = round_root / "candidate.npz"
            save_model_npz(model, candidate_path)
            row = {
                "round": round_index,
                "target_count": target_count,
                "field_tail": field_history[-3:],
                "ray_tail": ray_history[-3:],
                "global_metrics": global_metrics,
                "roi_metrics": roi_metrics,
            }
            if parent_metrics is not None:
                previous = rounds[-1] if rounds else parent_metrics
                row["progress_gate"] = recovery_progress(
                    global_metrics,
                    roi_metrics,
                    previous["global_metrics"],
                    previous["roi_metrics"],
                    baseline,
                )
                if (
                    not row["progress_gate"]["joint_tau_regression"]
                    and (
                        best is None
                        or row["progress_gate"]["score"] < best["score"]
                    )
                ):
                    best = {
                        "kind": "trained_round",
                        "round": round_index,
                        "target_count": target_count,
                        "path": str(candidate_path.resolve()),
                        "sha256": _sha256(candidate_path),
                        "score": row["progress_gate"]["score"],
                        "global_metrics": global_metrics,
                        "roi_metrics": roi_metrics,
                    }
            rounds = [
                previous
                for previous in rounds
                if previous["round"] != round_index
            ] + [row]
            rounds.sort(key=lambda item: item["round"])
            _write_json(
                round_root / "metrics.json",
                {
                    "baseline": baseline,
                    **row,
                },
            )
            if (
                stop_on_joint_tau_regression
                and row["progress_gate"]["joint_tau_regression"]
            ):
                summary = {
                    "status": "complete_stopped_regression",
                    "schedule": schedule,
                    "field_steps_per_round": field_steps,
                    "ray_steps_per_round": ray_steps_count,
                    "baseline": baseline,
                    "parent": parent_metrics,
                    "rounds": rounds,
                    "best": best,
                    "stopped_round": round_index,
                    "elapsed_minutes_this_process": (
                        time.perf_counter() - started
                    )
                    / 60.0,
                    "ue_deployed": False,
                }
                _write_json(summary_path, summary)
                save_checkpoint(
                    checkpoint,
                    model,
                    optimizer,
                    generator,
                    phase="stopped_regression",
                    round_index=round_index,
                    step=0,
                    densification_state={"schedule": schedule},
                    hashes=hashes,
                    index_settings={
                        "bin_size": 0.1,
                        "support_sigma": 3.0,
                        "rebuild_interval": 1,
                    },
                )
                return summary
            if (
                round_index == len(schedule) - 1
                and target_count != len(roi_indices)
            ):
                with torch.no_grad():
                    intermediate_centers = (
                        model.kernels()[0].detach().cpu().numpy()
                    )
                gates = {
                    "global_strict": quality_strict(
                        global_metrics, baseline["global"]
                    ),
                    "global_bounded": quality_bounded(
                        global_metrics, baseline["global"]
                    ),
                    "roi": roi_quality_gate(
                        roi_metrics, baseline["roi"]
                    ),
                }
                summary = {
                    "status": "complete_intermediate",
                    "schedule": schedule,
                    "field_steps_per_round": field_steps,
                    "ray_steps_per_round": ray_steps_count,
                    "baseline": baseline,
                    "parent": parent_metrics,
                    "rounds": rounds,
                    "best": best,
                    "gates": gates,
                    "lattice": {
                        "g2_roi": lattice_order(
                            all_centers[roi_indices],
                            roi_report["block_size"] * source.voxel_m,
                        ),
                        "candidate": lattice_order(
                            intermediate_centers,
                            roi_report["block_size"] * source.voxel_m,
                        ),
                    },
                    "elapsed_minutes_this_process": (
                        time.perf_counter() - started
                    )
                    / 60.0,
                    "ue_deployed": False,
                }
                _write_json(summary_path, summary)
                save_checkpoint(
                    checkpoint,
                    model,
                    optimizer,
                    generator,
                    phase="complete",
                    round_index=round_index,
                    step=0,
                    densification_state={"schedule": schedule},
                    hashes=hashes,
                    index_settings={
                        "bin_size": 0.1,
                        "support_sigma": 3.0,
                        "rebuild_interval": 1,
                    },
                )
                return summary
            if round_index == len(schedule) - 1:
                with torch.no_grad():
                    candidate_centers, candidate_covariance, _, _, candidate_extinction = (
                        model.kernels()
                    )
                candidate_centers_np = candidate_centers.detach().cpu().numpy()
                candidate_covariance_np = (
                    candidate_covariance.detach().cpu().numpy()
                )
                candidate_extinction_np = (
                    candidate_extinction.detach().cpu().numpy()
                )
                recovered_centers = all_centers.copy()
                recovered_covariance = all_covariance.copy()
                recovered_extinction = all_extinction.copy()
                recovered_centers[roi_indices] = candidate_centers_np
                recovered_covariance[roi_indices] = candidate_covariance_np
                recovered_extinction[roi_indices] = candidate_extinction_np
                recovered_path = root / "recovered_hybrid_404524.npz"
                with recovered_path.with_suffix(".npz.tmp").open("wb") as stream:
                    np.savez_compressed(
                        stream,
                        center_m=recovered_centers.astype(np.float32),
                        covariance_m2=recovered_covariance.astype(np.float32),
                        sigma_t_per_m=recovered_extinction.astype(np.float32),
                    )
                recovered_path.with_suffix(".npz.tmp").replace(recovered_path)
                pitch_m = (
                    roi_report["block_size"] * source.voxel_m
                )
                lattice = {
                    "g2_roi": lattice_order(
                        all_centers[roi_indices], pitch_m
                    ),
                    "candidate_roi": lattice_order(
                        candidate_centers_np, pitch_m
                    ),
                }
                gates = {
                    "global_strict": quality_strict(
                        global_metrics, baseline["global"]
                    ),
                    "global_bounded": quality_bounded(
                        global_metrics, baseline["global"]
                    ),
                    "roi": roi_quality_gate(
                        roi_metrics, baseline["roi"]
                    ),
                }
                passed = (
                    (
                        gates["global_strict"]
                        or gates["global_bounded"]
                    )
                    and gates["roi"]
                )
                summary = {
                    "status": (
                        "complete_passed"
                        if passed
                        else "complete_failed"
                    ),
                    "schedule": schedule,
                    "field_steps_per_round": field_steps,
                    "ray_steps_per_round": ray_steps_count,
                    "baseline": baseline,
                    "parent": parent_metrics,
                    "rounds": rounds,
                    "best": best,
                    "gates": gates,
                    "lattice": lattice,
                    "recovered": str(recovered_path.resolve()),
                    "recovered_sha256": _sha256(recovered_path),
                    "elapsed_minutes_this_process": (
                        time.perf_counter() - started
                    )
                    / 60.0,
                    "ue_deployed": False,
                }
                _write_json(summary_path, summary)
                save_checkpoint(
                    checkpoint,
                    model,
                    optimizer,
                    generator,
                    phase="complete",
                    round_index=round_index,
                    step=0,
                    densification_state={"schedule": schedule},
                    hashes=hashes,
                    index_settings={
                        "bin_size": 0.1,
                        "support_sigma": 3.0,
                        "rebuild_interval": 1,
                    },
                )
                return summary
            next_count = schedule[round_index + 1]
            model, densification = densify_p2_candidate(
                model,
                frozen,
                source,
                halo_mask,
                roi_report["block_size"],
                next_count,
                reference_mass,
                generator,
                device,
                error_sample_count,
            )
            row["densification"] = densification
            optimizer = make_optimizer(
                model, geometry_lr=5e-4, extinction_lr=5e-4
            )
            round_index += 1
            phase, phase_step = "field", 0
            _write_json(
                summary_path,
                {
                    "status": "running",
                    "schedule": schedule,
                    "field_steps_per_round": field_steps,
                    "ray_steps_per_round": ray_steps_count,
                    "baseline": baseline,
                    "parent": parent_metrics,
                    "rounds": rounds,
                    "best": best,
                    "current_round": round_index,
                    "current_phase": phase,
                    "ue_deployed": False,
                },
            )
            save_checkpoint(
                checkpoint,
                model,
                optimizer,
                generator,
                phase=phase,
                round_index=round_index,
                step=0,
                densification_state={"schedule": schedule},
                hashes=hashes,
                index_settings={
                    "bin_size": 0.1,
                    "support_sigma": 3.0,
                    "rebuild_interval": 1,
                },
            )
    raise RuntimeError("P2 schedule exited without a final Gate")


def train_p2c(
    source_grid: Path,
    initializer: Path,
    dataset: Path,
    root: Path,
    device: torch.device,
    seed: int,
    resume: bool,
) -> dict:
    input_root = DEFAULT_P2_OUTPUT
    baseline = json.loads(
        (input_root / "baseline_metrics.json").read_text(encoding="utf-8")
    )
    summary_path = root / "summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("status", "").startswith("complete"):
            return summary
        if not resume:
            raise FileExistsError("P2c is running; use --resume")
        stages = summary.get("stages", [])
        stale_evaluations = int(summary.get("stale_evaluations", 0))
        best = summary["best"]
    else:
        stages = []
        stale_evaluations = 0
        with DEFAULT_P2C_FALLBACK_METRICS.open(
            "r", encoding="utf-8"
        ) as stream:
            fallback_metrics = json.load(stream)
        best = {
            "kind": "p2b_35k_fallback",
            "path": str(DEFAULT_P2C_FALLBACK.resolve()),
            "sha256": _sha256(DEFAULT_P2C_FALLBACK),
            "score": recovery_progress(
                fallback_metrics["global_metrics"],
                fallback_metrics["roi_metrics"],
                fallback_metrics["global_metrics"],
                fallback_metrics["roi_metrics"],
                baseline,
            )["score"],
            "global_metrics": fallback_metrics["global_metrics"],
            "roi_metrics": fallback_metrics["roi_metrics"],
        }

    if stages:
        warm_start = Path(stages[-1]["candidate"])
        parent_metrics = Path(stages[-1]["metrics"])
    else:
        warm_start = DEFAULT_P2C_WARM_START
        parent_metrics = DEFAULT_P2C_PARENT_METRICS

    totals = (40, 80, 120, 160, 200)
    started = time.perf_counter()
    for stage_index in range(len(stages), len(totals)):
        total_ray_steps = totals[stage_index]
        stage_root = root / f"stage_{total_ray_steps:04d}"
        previous = json.loads(parent_metrics.read_text(encoding="utf-8"))
        _write_json(
            summary_path,
            {
                "status": "running",
                "max_ray_steps": totals[-1],
                "ray_steps_per_evaluation": 40,
                "patience": 2,
                "current_total_ray_steps": total_ray_steps,
                "stale_evaluations": stale_evaluations,
                "stages": stages,
                "best": best,
                "ue_deployed": False,
            },
        )
        stage_report = train_p2(
            source_grid,
            initializer,
            dataset,
            stage_root,
            device,
            seed + stage_index,
            field_steps=0,
            ray_steps_count=40,
            sample_count=4_096,
            error_sample_count=60_000,
            resume=(stage_root / "checkpoint.pt").exists(),
            input_root=input_root,
            schedule=(40_000,),
            warm_start=warm_start,
            parent_metrics_path=parent_metrics,
        )
        current = stage_report["rounds"][-1]
        candidate = stage_root / "round_00_040000" / "candidate.npz"
        metrics_path = stage_root / "round_00_040000" / "metrics.json"
        global_improved = (
            current["global_metrics"]["tau_mae"]
            <= previous["global_metrics"]["tau_mae"] * 0.995
        )
        roi_improved = (
            current["roi_metrics"]["tau_mae"]
            <= previous["roi_metrics"]["tau_mae"] * 0.995
        )
        stale_evaluations = (
            0 if global_improved or roi_improved else stale_evaluations + 1
        )
        score = current["progress_gate"]["score"]
        if score < best["score"]:
            best = {
                "kind": "p2c_40k_recovery",
                "total_ray_steps": total_ray_steps,
                "path": str(candidate.resolve()),
                "sha256": _sha256(candidate),
                "score": score,
                "global_metrics": current["global_metrics"],
                "roi_metrics": current["roi_metrics"],
            }
        stages.append(
            {
                "total_ray_steps": total_ray_steps,
                "candidate": str(candidate.resolve()),
                "candidate_sha256": _sha256(candidate),
                "metrics": str(metrics_path.resolve()),
                "global_tau_improved_0p5pct": global_improved,
                "roi_tau_improved_0p5pct": roi_improved,
                "stale_evaluations": stale_evaluations,
                "global_metrics": current["global_metrics"],
                "roi_metrics": current["roi_metrics"],
            }
        )
        warm_start = candidate
        parent_metrics = metrics_path
        terminal = (
            "complete_stalled"
            if stale_evaluations >= 2
            else (
                "complete_max_steps"
                if total_ray_steps == totals[-1]
                else "running"
            )
        )
        summary = {
            "status": terminal,
            "max_ray_steps": totals[-1],
            "ray_steps_per_evaluation": 40,
            "patience": 2,
            "stale_evaluations": stale_evaluations,
            "stages": stages,
            "best": best,
            "elapsed_minutes_this_process": (
                time.perf_counter() - started
            )
            / 60.0,
            "ue_deployed": False,
        }
        _write_json(summary_path, summary)
        if terminal != "running":
            return summary
    raise RuntimeError("P2c recovery exited without a terminal summary")


def _timed_field(
    samples: torch.Tensor,
    centers: torch.Tensor,
    precisions: torch.Tensor,
    extinction: torch.Tensor,
    index: TorchSpatialIndex,
    support_sigma: float,
    repeats: int,
) -> tuple[list[float], list[float]]:
    forward_ms: list[float] = []
    backward_ms: list[float] = []
    for iteration in range(repeats + 1):
        for parameter in (centers, precisions, extinction):
            parameter.grad = None
        if samples.is_cuda:
            torch.cuda.synchronize(samples.device)
        started = time.perf_counter()
        field = evaluate_field(
            samples, centers, precisions, extinction, index, support_sigma
        )
        if samples.is_cuda:
            torch.cuda.synchronize(samples.device)
        forward = (time.perf_counter() - started) * 1000.0
        started = time.perf_counter()
        field.mean().backward()
        if samples.is_cuda:
            torch.cuda.synchronize(samples.device)
        backward = (time.perf_counter() - started) * 1000.0
        if iteration:
            forward_ms.append(forward)
            backward_ms.append(backward)
    return forward_ms, backward_ms


def benchmark(
    source: Path,
    counts: list[int],
    sample_count: int,
    bin_size: float,
    support_sigma: float,
    max_bins_per_gaussian: int,
    repeats: int,
    device: torch.device,
    seed: int,
) -> dict:
    data = np.load(source)
    all_centers = np.asarray(data["center_m"], dtype=np.float32)
    all_covariances = np.asarray(data["covariance_m2"], dtype=np.float32)
    all_extinction = np.asarray(data["sigma_t_per_m"], dtype=np.float32)
    if (
        all_covariances.shape != (len(all_centers), 3, 3)
        or all_extinction.shape != (len(all_centers),)
        or max(counts) > len(all_centers)
    ):
        raise ValueError("benchmark counts exceed a valid initializer")

    rows = []
    rng = np.random.default_rng(seed)
    for count in counts:
        selected = (
            np.arange(count)
            if count == len(all_centers)
            else np.linspace(0, len(all_centers) - 1, count, dtype=np.int64)
        )
        centers_np = all_centers[selected]
        covariances_np = all_covariances[selected]
        extinction_np = all_extinction[selected]
        started = time.perf_counter()
        index = build_spatial_index(
            centers_np,
            covariances_np,
            bin_size,
            support_sigma,
            max_bins_per_gaussian,
        )
        build_ms = (time.perf_counter() - started) * 1000.0
        sample_sources = rng.integers(0, count, size=sample_count)
        samples_np = centers_np[sample_sources] + rng.uniform(
            -0.5 * bin_size, 0.5 * bin_size, size=(sample_count, 3)
        ).astype(np.float32)
        coordinates = np.floor(
            (samples_np - index.origin) / index.bin_size
        ).astype(np.int64)
        limits = np.asarray(index.shape)
        valid = np.all((coordinates >= 0) & (coordinates < limits), axis=1)
        bins = (
            coordinates[valid, 0]
            + index.shape[0]
            * (
                coordinates[valid, 1]
                + index.shape[1] * coordinates[valid, 2]
            )
        )
        neighbors = index.cell_offsets[bins + 1] - index.cell_offsets[bins]

        if device.type == "cuda":
            torch.cuda.empty_cache()
            torch.cuda.reset_peak_memory_stats(device)
        centers = torch.tensor(
            centers_np, dtype=torch.float32, device=device, requires_grad=True
        )
        precisions = torch.tensor(
            np.linalg.inv(covariances_np),
            dtype=torch.float32,
            device=device,
            requires_grad=True,
        )
        extinction = torch.tensor(
            extinction_np, dtype=torch.float32, device=device, requires_grad=True
        )
        samples = torch.tensor(samples_np, dtype=torch.float32, device=device)
        torch_index = index.to(device)
        allocated_before = (
            torch.cuda.memory_allocated(device) / 2**20
            if device.type == "cuda"
            else 0.0
        )
        forward_ms, backward_ms = _timed_field(
            samples,
            centers,
            precisions,
            extinction,
            torch_index,
            support_sigma,
            repeats,
        )
        peak_allocated = (
            torch.cuda.max_memory_allocated(device) / 2**20
            if device.type == "cuda"
            else 0.0
        )
        peak_reserved = (
            torch.cuda.max_memory_reserved(device) / 2**20
            if device.type == "cuda"
            else 0.0
        )
        rows.append(
            {
                "gaussian_count": count,
                "sample_count": sample_count,
                "bin_size_m": bin_size,
                "support_sigma": support_sigma,
                "index_shape": index.shape,
                "cell_count": len(index.cell_offsets) - 1,
                "pair_count": len(index.gaussian_ids),
                "pairs_per_gaussian": len(index.gaussian_ids) / count,
                "neighbors_per_sample_p50_p95_p99_max": np.percentile(
                    neighbors, (50, 95, 99, 100)
                ).tolist(),
                "index_build_ms": build_ms,
                "field_forward_ms_median": float(np.median(forward_ms)),
                "field_backward_ms_median": float(np.median(backward_ms)),
                "gpu_allocated_before_eval_mib": allocated_before,
                "gpu_peak_allocated_mib": peak_allocated,
                "gpu_peak_increment_mib": peak_allocated - allocated_before,
                "gpu_peak_reserved_mib": peak_reserved,
                "all_gradients_finite": all(
                    parameter.grad is not None
                    and bool(torch.isfinite(parameter.grad).all())
                    for parameter in (centers, precisions, extinction)
                ),
            }
        )
        del centers, precisions, extinction, samples, torch_index
        if device.type == "cuda":
            torch.cuda.empty_cache()

    return {
        "status": "complete",
        "source": str(source.resolve()),
        "source_sha256": _sha256(source),
        "device": str(device),
        "gpu": (
            torch.cuda.get_device_name(device) if device.type == "cuda" else None
        ),
        "seed": seed,
        "repeats": repeats,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-npz", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--source-grid", type=Path, default=DEFAULT_GRID)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--counts", type=int, nargs="+", default=(50_000, 404_524))
    parser.add_argument("--samples", type=int, default=16_384)
    parser.add_argument("--bin-size-m", type=float, default=0.10)
    parser.add_argument("--support-sigma", type=float, default=3.0)
    parser.add_argument("--max-bins-per-gaussian", type=int, default=256)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=20_260_729)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--trainer-self-check", action="store_true")
    parser.add_argument("--real-smoke", action="store_true")
    parser.add_argument("--prepare-roi", action="store_true")
    parser.add_argument("--p2-dry-run", action="store_true")
    parser.add_argument("--train-p2", action="store_true")
    parser.add_argument("--train-p2b", action="store_true")
    parser.add_argument("--train-p2c", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--field-steps", type=int, default=80)
    parser.add_argument("--ray-steps", type=int, default=5)
    parser.add_argument("--p2b-ray-steps", type=int, default=40)
    parser.add_argument("--field-samples", type=int, default=4_096)
    parser.add_argument("--error-samples", type=int, default=60_000)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--roi-count", type=int, default=50_000)
    parser.add_argument("--block-size", type=int, default=8)
    args = parser.parse_args()
    if (
        not args.counts
        or min(args.counts) <= 0
        or args.samples <= 0
        or args.repeats <= 0
    ):
        parser.error("counts, samples and repeats must be positive")
    output = args.output_dir.resolve()
    if (
        sum(
            (
                args.self_check,
                args.trainer_self_check,
                args.real_smoke,
                args.prepare_roi,
                args.p2_dry_run,
                args.train_p2,
                args.train_p2b,
                args.train_p2c,
            )
        )
        > 1
    ):
        parser.error("choose one check or benchmark")
    if (
        args.field_steps <= 0
        or args.ray_steps <= 0
        or args.p2b_ray_steps <= 0
        or args.field_samples <= 0
        or args.error_samples <= 0
    ):
        parser.error("P2 step and sample counts must be positive")
    if args.self_check:
        report = self_check()
        _write_json(output / "self_check.json", report)
        print(json.dumps(report, indent=2))
        return
    if args.trainer_self_check:
        report = trainer_self_check()
        _write_json(DEFAULT_P1_OUTPUT / "resume_check.json", report)
        print(json.dumps(report, indent=2))
        return
    if args.real_smoke:
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            parser.error("CUDA device requested but CUDA is unavailable")
        report = real_smoke(
            args.source_grid.resolve(),
            args.input_npz.resolve(),
            args.counts[0],
            args.samples,
            device,
            args.seed,
        )
        _write_json(DEFAULT_P1_OUTPUT / "real_smoke.json", report)
        print(json.dumps(report, indent=2))
        return
    if args.prepare_roi:
        report = prepare_roi(
            args.source_grid.resolve(),
            args.input_npz.resolve(),
            args.dataset.resolve(),
            DEFAULT_P2_OUTPUT,
            args.roi_count,
            args.block_size,
            args.seed,
        )
        print(json.dumps(report, indent=2))
        return
    if args.p2_dry_run:
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            parser.error("CUDA device requested but CUDA is unavailable")
        report = p2_dry_run(
            args.source_grid.resolve(),
            args.input_npz.resolve(),
            args.dataset.resolve(),
            DEFAULT_P2_OUTPUT,
            args.counts[0],
            args.samples,
            device,
            args.seed,
        )
        print(json.dumps(report, indent=2))
        return
    if args.train_p2:
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            parser.error("CUDA device requested but CUDA is unavailable")
        report = train_p2(
            args.source_grid.resolve(),
            args.input_npz.resolve(),
            args.dataset.resolve(),
            DEFAULT_P2_OUTPUT,
            device,
            args.seed,
            args.field_steps,
            args.ray_steps,
            args.field_samples,
            args.error_samples,
            args.resume,
        )
        print(json.dumps(report, indent=2))
        return
    if args.train_p2b:
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            parser.error("CUDA device requested but CUDA is unavailable")
        report = train_p2(
            args.source_grid.resolve(),
            args.input_npz.resolve(),
            args.dataset.resolve(),
            DEFAULT_P2B_OUTPUT,
            device,
            args.seed,
            args.field_steps,
            args.p2b_ray_steps,
            args.field_samples,
            args.error_samples,
            args.resume,
            input_root=DEFAULT_P2_OUTPUT,
            schedule=(30_000, 35_000, 40_000, 45_000, 50_000),
            warm_start=DEFAULT_P2B_WARM_START,
            parent_metrics_path=DEFAULT_P2B_PARENT_METRICS,
            stop_on_joint_tau_regression=True,
        )
        print(json.dumps(report, indent=2))
        return
    if args.train_p2c:
        device = torch.device(args.device)
        if device.type == "cuda" and not torch.cuda.is_available():
            parser.error("CUDA device requested but CUDA is unavailable")
        report = train_p2c(
            args.source_grid.resolve(),
            args.input_npz.resolve(),
            args.dataset.resolve(),
            DEFAULT_P2C_OUTPUT,
            device,
            args.seed,
            args.resume,
        )
        print(json.dumps(report, indent=2))
        return
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA device requested but CUDA is unavailable")
    report = benchmark(
        args.input_npz.resolve(),
        list(args.counts),
        args.samples,
        args.bin_size_m,
        args.support_sigma,
        args.max_bins_per_gaussian,
        args.repeats,
        device,
        args.seed,
    )
    _write_json(output / "benchmark.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
