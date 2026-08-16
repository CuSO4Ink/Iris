import math
import unittest

import numpy as np

from evaluate_heldout import compute_metrics


class HeldoutMetricsTest(unittest.TestCase):
    def test_reference_mask_excludes_background_from_tau_metrics(self) -> None:
        reference_t = np.array([[1.0, 0.9], [0.5, 0.1]])
        candidate_tau = -np.log(reference_t)
        candidate_tau[0, 0] = 5.0  # Deliberately wrong only in reference background.

        metrics = compute_metrics(reference_t, candidate_tau, alpha_threshold=0.05)

        self.assertTrue(math.isinf(metrics["tau_psnr_db"]))
        self.assertEqual(metrics["tau_mae"], 0.0)
        self.assertEqual(metrics["foreground_pixels"], 3)
        self.assertAlmostEqual(metrics["silhouette_iou"], 0.75)
        self.assertFalse(math.isinf(metrics["transmittance_psnr_full_db"]))


if __name__ == "__main__":
    unittest.main()
