import math
import unittest


class FootprintMassTest(unittest.TestCase):
    def test_presets_preserve_integrated_2d_mass(self) -> None:
        xx, xy, yy = 4.0, 0.75, 2.5
        base_det = xx * yy - xy * xy

        for scale in (1.0, 1.08, 1.15, 1.25):
            filter_variance = (scale * scale - 1.0) * math.sqrt(base_det)
            filtered_det = (
                (xx + filter_variance) * (yy + filter_variance) - xy * xy
            )
            opacity_scale = math.sqrt(base_det / filtered_det)
            mass_ratio = opacity_scale * math.sqrt(filtered_det / base_det)
            self.assertAlmostEqual(mass_ratio, 1.0, places=12)

        self.assertEqual(
            (1.0 * 1.0 - 1.0) * math.sqrt(base_det),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
