"""Convert DSYG/GFields Gaussian PLY primitives to GaussianVolume JSON."""

from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path


def read_binary_ply(path: Path) -> tuple[list[str], list[tuple[float, ...]]]:
    if path.is_dir():
        files = sorted((path / "data").glob("root.primitives_pyr*.ply"))
        if not files:
            raise ValueError(f"Asset directory has no primitive PLY files: {path}")
        properties, rows = read_binary_ply(files[0])
        for source in files[1:]:
            next_properties, next_rows = read_binary_ply(source)
            if next_properties != properties:
                raise ValueError("Pyramid levels use different PLY properties")
            rows.extend(next_rows)
        return properties, rows

    with path.open("rb") as stream:
        if stream.readline().strip() != b"ply":
            raise ValueError("Not a PLY file")

        vertex_count = 0
        properties: list[str] = []
        in_vertices = False
        while True:
            line = stream.readline()
            if not line:
                raise ValueError("PLY header has no end_header")
            words = line.decode("ascii").strip().split()
            if words[:2] == ["format", "binary_little_endian"]:
                pass
            elif words[:2] == ["element", "vertex"]:
                vertex_count = int(words[2])
                in_vertices = True
            elif words[:1] == ["element"]:
                in_vertices = False
            elif in_vertices and words[:2] == ["property", "float"]:
                properties.append(words[2])
            elif words[:1] == ["end_header"]:
                break

        if not vertex_count or not properties:
            raise ValueError("PLY has no float vertex payload")
        record = struct.Struct("<" + "f" * len(properties))
        rows = [record.unpack(stream.read(record.size)) for _ in range(vertex_count)]
        if any(len(row) != len(properties) for row in rows):
            raise ValueError("Truncated PLY vertex payload")
        return properties, rows


def convert(
    source: Path,
    output: Path,
    world_scale: float,
    density_multiplier: float,
    albedo_override: tuple[float, float, float] | None = None,
) -> dict:
    if world_scale <= 0.0 or density_multiplier <= 0.0:
        raise ValueError("scale and density multiplier must be positive")
    if albedo_override is not None and (
        len(albedo_override) != 3
        or not all(math.isfinite(value) and value >= 0.0 for value in albedo_override)
    ):
        raise ValueError("albedo override must contain three finite non-negative values")

    properties, rows = read_binary_ply(source)
    required = {
        "x", "y", "z", "scale_0", "scale_1", "scale_2",
        "rot_0", "rot_1", "rot_2", "rot_3",
        "albedo_0", "albedo_1", "albedo_2",
    }
    missing = required.difference(properties)
    if missing:
        raise ValueError(f"Missing PLY properties: {sorted(missing)}")

    density_property = next(
        (name for name in ("sigma_t_0", "opacities_0") if name in properties),
        None,
    )
    if density_property is None:
        raise ValueError("PLY has neither sigma_t_0 nor opacities_0")

    index = {name: i for i, name in enumerate(properties)}
    normalizer = (2.0 * math.pi) ** 1.5
    gaussians = []
    for row_index, row in enumerate(rows):
        if not all(math.isfinite(value) for value in row):
            raise ValueError(f"Non-finite value in PLY row {row_index}")
        omega = row[index["omega_0"]] if "omega_0" in index else 0.0
        if omega < 0.0:
            raise ValueError(f"Negative Gabor frequency in PLY row {row_index}")

        source_scale = [math.exp(row[index[f"scale_{axis}"]]) for axis in range(3)]
        source_volume = math.prod(source_scale)
        density_weight = row[index[density_property]]
        if density_weight < 0.0 and math.isclose(omega, 0.0, abs_tol=1e-6):
            raise ValueError(f"Negative Gaussian density in PLY row {row_index}")
        sigma_t = (
            density_weight * density_multiplier
            / (normalizer * source_volume * world_scale)
        )
        gaussians.append({
            "center": [row[index[axis]] * world_scale for axis in ("x", "y", "z")],
            "scale": [value * world_scale for value in source_scale],
            # PLY stores (w, x, y, z); UE JSON stores (x, y, z, w).
            "rotation": [row[index[f"rot_{axis}"]] for axis in (1, 2, 3, 0)],
            "sigma_t": sigma_t,
            "omega": omega,
            "albedo": list(albedo_override) if albedo_override is not None else [
                row[index[f"albedo_{axis}"]] for axis in range(3)
            ],
            "emission": 0.0,
        })

    payload = {
        "schema": "GaussianVolume.Primitives.v1",
        "source": str(source.as_posix()),
        "world_scale": world_scale,
        "density_multiplier": density_multiplier,
        "density_property": density_property,
        "density_conversion": "normalized_3d_gaussian_to_peak_extinction",
        "albedo_source": "override" if albedo_override is not None else "ply",
        "primitive_count": len(gaussians),
        "gabor_count": sum(not math.isclose(g["omega"], 0.0, abs_tol=1e-6) for g in gaussians),
        "gaussians": gaussians,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--world-scale", type=float, default=500.0)
    parser.add_argument("--density-multiplier", type=float, default=10.0)
    parser.add_argument(
        "--albedo",
        type=float,
        nargs=3,
        metavar=("R", "G", "B"),
        help="Override PLY albedo for UE shading without changing the fitted density",
    )
    args = parser.parse_args()
    if args.world_scale <= 0.0 or args.density_multiplier <= 0.0:
        parser.error("scale and density multiplier must be positive")
    payload = convert(
        args.source,
        args.output,
        args.world_scale,
        args.density_multiplier,
        tuple(args.albedo) if args.albedo is not None else None,
    )
    print(f"Wrote {payload['primitive_count']} primitives to {args.output}")


if __name__ == "__main__":
    main()
