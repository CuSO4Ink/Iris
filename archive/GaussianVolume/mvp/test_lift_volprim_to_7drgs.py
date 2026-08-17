import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch
from plyfile import PlyData

from grid_to_7drgs import (
    COMPACT_PROPERTIES,
    LIGHT_DIRECTIONS_GL,
    _directional_transmittance,
    convert as convert_grid,
    convert_initializer,
)
from lift_volprim_to_7drgs import PLY_PROPERTIES, convert
from prepare_7drgs_dataset import SH1_BASIS, _write_init_from_b2

TRAINING_ROOT = Path(__file__).parents[1] / "training" / "7drgs"
sys.path.insert(0, str(TRAINING_ROOT))
from utils.loss_utils import bounded_parameter_regularization
from utils.sh_utils import eval_sh
from utils.slicing_utils import slice_gaussian_dynamic


class LiftVolprimTo7DRGSTest(unittest.TestCase):
    def test_identity_gaussian_maps_ue_axes_and_covariance_to_gl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            output = root / "output.ply"
            source.write_text(json.dumps({"gaussians": [{
                "center": [100.0, 200.0, 300.0],
                "scale": [100.0, 200.0, 300.0],
                "rotation": [0.0, 0.0, 0.0, 1.0],
                "sigma_t": 0.01,
            }]}), encoding="utf-8")

            result = convert(source, output)
            self.assertEqual(result["point_count"], 1)
            with output.open("rb") as stream:
                while stream.readline().strip() != b"end_header":
                    pass
                row = struct.unpack("<" + "f" * len(PLY_PROPERTIES), stream.read())
            values = dict(zip(PLY_PROPERTIES, row))
            self.assertEqual((values["x"], values["y"], values["z"]), (1.0, -3.0, -2.0))
            self.assertAlmostEqual(math.exp(values["chol_diag_0"]), 1.0, places=6)
            self.assertAlmostEqual(math.exp(values["chol_diag_1"]), 3.0, places=6)
            self.assertAlmostEqual(math.exp(values["chol_diag_2"]), 2.0, places=6)
            self.assertGreater(1.0 / (1.0 + math.exp(-values["opacity"])), 0.0)

    def test_dense_grid_expands_to_six_relight_lobes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "grid.npy"
            output = root / "grid.ply"
            grid = np.zeros((4, 4, 4), dtype=np.float32)
            grid[0:2, 0:2, 0:2] = 0.25
            np.save(source, grid)

            result = convert_grid(source, output, block_size=2, longest_size_cm=4.0)
            with output.open("rb") as stream:
                header_lines = []
                while True:
                    line = stream.readline()
                    header_lines.append(line)
                    if line.strip() == b"end_header":
                        break
                rows = [
                    struct.unpack("<" + "f" * len(PLY_PROPERTIES), stream.read(
                        4 * len(PLY_PROPERTIES)
                    ))
                    for _ in range(6)
                ]
            index = {name: i for i, name in enumerate(PLY_PROPERTIES)}

            self.assertEqual(result["spatial_points"], 1)
            self.assertEqual(result["point_count"], 6)
            self.assertIn(b"element vertex 6\n", header_lines)
            for row, expected_direction in zip(rows, LIGHT_DIRECTIONS_GL):
                actual = row[index["mu_d_0"]:index["mu_d_2"] + 1]
                self.assertTrue(np.allclose(actual, expected_direction))
                self.assertGreater(row[index["opacity"]], -20.0)

    def test_compact_grid_keeps_one_64_byte_record_per_spatial_point(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "grid.npy"
            output = root / "compact.ply"
            np.save(source, np.ones((2, 2, 2), dtype=np.float32))

            result = convert_grid(
                source, output, block_size=2, longest_size_cm=4.0, compact=True
            )
            with output.open("rb") as stream:
                header = b""
                while not header.endswith(b"end_header\n"):
                    header += stream.readline()
                row = struct.unpack("<" + "f" * len(COMPACT_PROPERTIES), stream.read())

            values = dict(zip(COMPACT_PROPERTIES, row))
            self.assertEqual(result["point_count"], 1)
            self.assertEqual(result["expanded_equivalent"], 6)
            self.assertEqual(output.stat().st_size - len(header), 64)
            self.assertIn(b"comment compact_static_transport 1\n", header)
            self.assertGreater(values["lobe_opacity"], 0.0)
            self.assertTrue(all(math.isfinite(values[f"j_{index}"]) for index in range(6)))

    def test_density_scale_controls_directional_shadowing(self) -> None:
        grid = np.ones((2, 1, 1), dtype=np.float32)
        sample = np.asarray(((0, 0, 0),), dtype=np.int32)
        light = _directional_transmittance(grid, sample, 1.0, 0.25)
        self.assertAlmostEqual(light[0, 0], math.exp(-0.5), places=6)
        self.assertAlmostEqual(light[1, 0], math.exp(-0.25), places=6)

    def test_fixed_budget_initializer_exports_one_compact_record_per_kernel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "initializer.npz"
            grid = root / "grid.npy"
            output = root / "compact.ply"
            covariance = np.eye(3, dtype=np.float32)[None] * 0.01
            np.savez(
                source,
                center_m=np.zeros((1, 3), dtype=np.float32),
                covariance_m2=covariance,
                sigma_t_per_m=np.ones(1, dtype=np.float32),
            )
            np.save(grid, np.ones((2, 2, 2), dtype=np.float32))

            result = convert_initializer(
                source, grid, output, voxel_cm=1.0, density_scale=0.25,
                angular_sigma=0.5, ambient=0.05,
            )
            with output.open("rb") as stream:
                header = b""
                while not header.endswith(b"end_header\n"):
                    header += stream.readline()
                row = dict(zip(
                    COMPACT_PROPERTIES,
                    struct.unpack("<" + "f" * len(COMPACT_PROPERTIES), stream.read()),
                ))

            kernel_sum = 1.0 + math.exp(-4.0) + 4.0 * math.exp(-2.0)
            expected = (1.0 - math.exp(-math.sqrt(2.0 * math.pi) * 0.1)) / kernel_sum
            self.assertEqual(result["point_count"], 1)
            self.assertEqual(output.stat().st_size - len(header), 64)
            self.assertAlmostEqual(row["lobe_opacity"], expected, places=6)
            self.assertTrue(all(0.05 <= row[f"j_{index}"] <= 1.0 for index in range(6)))

    def test_six_leaf_b2_aggregates_density_and_light_sh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            grid_path = root / "grid.npy"
            teacher_path = root / "teacher.ply"
            init_path = root / "init.ply"
            grid = np.zeros((2, 2, 2), dtype=np.float32)
            grid[0, 0, 0] = 0.25
            grid[1, 1, 1] = 0.75
            np.save(grid_path, grid)
            convert_grid(
                grid_path,
                teacher_path,
                block_size=1,
                longest_size_cm=2.0,
                density_scale=0.2,
                angular_sigma=0.5,
                ambient=0.0,
            )

            report = _write_init_from_b2(teacher_path, init_path)
            output = PlyData.read(init_path).elements[0].data.copy()
            self.assertEqual(report["spatial_points"], 2)
            self.assertEqual(len(output), 2)
            self.assertLess(float(output["lambda_d"][0]), -10.0)
            self.assertTrue(all(
                np.allclose(output[f"chol_offdiag_{index}"], 0.0)
                for index in range(3, 21)
            ))
            coefficients = np.stack(
                [
                    output["f_dc_j"],
                    output["f_rest_j_0"],
                    output["f_rest_j_1"],
                    output["f_rest_j_2"],
                ]
            )
            fitted = SH1_BASIS @ coefficients + 0.5
            self.assertTrue(np.isfinite(fitted).all())
            self.assertGreater(float(np.ptp(fitted[:, 0])), 0.0)
            self.assertGreater(float(1.0 / (1.0 + np.exp(-output["opacity"][0]))), 0.0)

    def test_python_slice_matches_ue_quarter_exponent(self) -> None:
        sigma = torch.eye(7).unsqueeze(0)
        _, _, factor = slice_gaussian_dynamic(
            mu_p=torch.zeros((1, 3)),
            mu_t=torch.zeros((1, 1)),
            mu_d=torch.tensor([[1.0, 0.0, 0.0]]),
            t=torch.zeros((1, 1)),
            d=torch.tensor([[-1.0, 0.0, 0.0]]),
            sigma=sigma,
            lambda_t=torch.ones((1, 1)),
            lambda_d=torch.ones((1, 1)),
        )
        self.assertAlmostEqual(float(factor), math.exp(-1.0), places=5)

    def test_bounded_regularizers_change_loss_and_gradient(self) -> None:
        rest = torch.full((2, 3, 1), 2.0, requires_grad=True)
        rest_t = torch.full((2, 3, 1), -2.0, requires_grad=True)
        diag = torch.full((2, 7), 7.0, requires_grad=True)
        offdiag = torch.full((2, 21), 5.0, requires_grad=True)
        sh_reg, sigma_reg = bounded_parameter_regularization(
            rest, rest_t, (diag, offdiag)
        )
        loss = sh_reg + sigma_reg
        loss.backward()
        self.assertGreater(float(loss.detach()), 0.0)
        for value in (rest, rest_t, diag, offdiag):
            self.assertGreater(float(value.grad.abs().sum()), 0.0)

    def test_zero_initialized_degree_two_preserves_degree_one(self) -> None:
        torch.manual_seed(0)
        directions = torch.nn.functional.normalize(torch.randn(7, 3), dim=1)
        degree_one = torch.randn(7, 3, 4)
        degree_two = torch.zeros(7, 3, 9)
        degree_two[:, :, :4] = degree_one
        self.assertTrue(torch.equal(
            eval_sh(1, degree_one, directions),
            eval_sh(2, degree_two, directions),
        ))


if __name__ == "__main__":
    unittest.main()
