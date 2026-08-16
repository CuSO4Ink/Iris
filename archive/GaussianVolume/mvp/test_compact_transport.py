import math
import random
import unittest


class CompactTransportTest(unittest.TestCase):
    def test_grouped_leaf_blend_and_dgsm_tau_match_expanded_records(self) -> None:
        random.seed(7)
        for _ in range(100):
            opacity = random.random() * 0.3
            falloff = random.random()
            weights = [random.random() for _ in range(6)]
            radiance = [random.random() for _ in range(6)]
            expanded_j = 0.0
            expanded_t = 1.0
            for weight, value in zip(weights, radiance):
                alpha = min(0.99, opacity * weight * falloff)
                if alpha < 1.0 / 255.0:
                    alpha = 0.0
                expanded_j = value * alpha + expanded_j * (1.0 - alpha)
                expanded_t *= 1.0 - alpha

            grouped_j = 0.0
            grouped_t = 1.0
            for weight, value in zip(weights, radiance):
                alpha = min(0.99, opacity * weight * falloff)
                if alpha >= 1.0 / 255.0:
                    grouped_j = value * alpha + grouped_j * (1.0 - alpha)
                    grouped_t *= 1.0 - alpha

            self.assertAlmostEqual(grouped_j, expanded_j, places=12)
            self.assertAlmostEqual(grouped_t, expanded_t, places=12)

            center_t = math.prod(1.0 - opacity * weight for weight in weights)
            expanded_tau = sum(-math.log(1.0 - opacity * weight) for weight in weights)
            self.assertAlmostEqual(-math.log(center_t), expanded_tau, places=12)


if __name__ == "__main__":
    unittest.main()
