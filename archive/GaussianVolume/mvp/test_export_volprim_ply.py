import json
import math
import struct
import tempfile
import unittest
from pathlib import Path

from export_volprim_ply import convert


PROPERTIES = [
    "x", "y", "z", "scale_0", "scale_1", "scale_2",
    "rot_0", "rot_1", "rot_2", "rot_3",
    "albedo_0", "albedo_1", "albedo_2", "omega_0",
]


def write_ply(path: Path, density_name: str, omega: float, density: float = 2.0) -> None:
    properties = [*PROPERTIES, density_name]
    values = [
        1.0, 2.0, 3.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0,
        0.8, 0.9, 1.0, omega, density,
    ]
    header = ["ply", "format binary_little_endian 1.0", "element vertex 1"]
    header.extend(f"property float {name}" for name in properties)
    header.extend(["end_header", ""])
    path.write_bytes(
        "\n".join(header).encode("ascii")
        + struct.pack("<" + "f" * len(values), *values)
    )


class ExportVolprimPlyTest(unittest.TestCase):
    def test_density_aliases_convert_to_the_same_gaussian(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for density_name in ("sigma_t_0", "opacities_0"):
                with self.subTest(density_name=density_name):
                    source = root / f"{density_name}.ply"
                    output = root / f"{density_name}.json"
                    write_ply(source, density_name, omega=0.0)
                    convert(source, output, world_scale=2.0, density_multiplier=1.0)
                    payload = json.loads(output.read_text(encoding="utf-8"))
                    gaussian = payload["gaussians"][0]
                    self.assertEqual(gaussian["center"], [2.0, 4.0, 6.0])
                    self.assertEqual(gaussian["scale"], [2.0, 2.0, 2.0])
                    self.assertEqual(gaussian["rotation"], [0.0, 0.0, 0.0, 1.0])
                    self.assertAlmostEqual(
                        gaussian["sigma_t"],
                        2.0 / ((2.0 * math.pi) ** 1.5 * 2.0),
                    )

    def test_signed_gabor_is_exported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gabor.ply"
            write_ply(source, "opacities_0", omega=1.0, density=-2.0)
            payload = convert(source, source.with_suffix(".json"), 1.0, 1.0)
            self.assertEqual(payload["gabor_count"], 1)
            self.assertEqual(payload["gaussians"][0]["omega"], 1.0)
            self.assertLess(payload["gaussians"][0]["sigma_t"], 0.0)

    def test_asset_directory_combines_gaussian_and_gabor_levels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "asset"
            data = source / "data"
            data.mkdir(parents=True)
            write_ply(data / "root.primitives_pyr0.ply", "opacities_0", omega=0.0)
            write_ply(data / "root.primitives_pyr1.ply", "opacities_0", omega=1.0)
            payload = convert(source, source.with_suffix(".json"), 1.0, 1.0)
            self.assertEqual(payload["primitive_count"], 2)
            self.assertEqual(payload["gabor_count"], 1)

    def test_albedo_override_keeps_density_fit_separate_from_ue_shading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "gaussian.ply"
            output = source.with_suffix(".json")
            write_ply(source, "opacities_0", omega=0.0)
            payload = convert(
                source,
                output,
                world_scale=1.0,
                density_multiplier=1.0,
                albedo_override=(0.6, 0.7, 0.8),
            )
            self.assertEqual(payload["gaussians"][0]["albedo"], [0.6, 0.7, 0.8])
            self.assertEqual(payload["albedo_source"], "override")


if __name__ == "__main__":
    unittest.main()
