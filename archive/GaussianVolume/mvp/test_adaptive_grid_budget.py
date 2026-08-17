import unittest

import numpy as np

from build_adaptive_grid_budget import (
    boost_anisotropy,
    choose_merge_targets,
    match_split_moments,
    mixture_moments,
)
from grid_to_7drgs import _aggregate_grid, _aggregate_grid_chunked


class AdaptiveGridBudgetTest(unittest.TestCase):
    def test_chunked_grid_aggregation_matches_dense(self) -> None:
        rng = np.random.default_rng(4)
        grid = rng.random((7, 6, 9), dtype=np.float32)
        grid[grid < 0.45] = 0.0
        dense = _aggregate_grid(grid, 2, 0.38)
        chunked = _aggregate_grid_chunked(grid, 2, 0.38)
        for actual, expected in zip(chunked, dense):
            np.testing.assert_allclose(actual, expected, rtol=1e-10, atol=1e-10)

    def test_split_matches_parent_mass_center_and_covariance(self) -> None:
        parent_centers = np.asarray(((0.0, 0.0, 0.0), (2.0, 1.0, -1.0)))
        parent_covariances = np.asarray(
            (np.diag((2.0, 1.0, 0.5)), np.diag((1.5, 0.75, 0.25)))
        )
        parent_masses = np.asarray((3.0, 5.0))
        child_centers = np.asarray(
            ((-0.5, 0.0, 0.0), (0.75, 0.2, 0.0), (1.5, 1.0, -1.0), (2.5, 1.2, -0.8))
        )
        child_covariances = np.repeat((np.eye(3) * 0.1)[None], 4, axis=0)
        child_masses = np.asarray((1.0, 2.0, 2.0, 1.0))
        child_parent = np.asarray((0, 0, 1, 1))

        centers, covariances, masses, report = match_split_moments(
            parent_centers,
            parent_covariances,
            parent_masses,
            child_centers,
            child_covariances,
            child_masses,
            child_parent,
            np.asarray((0, 1)),
        )

        for parent in range(2):
            members = child_parent == parent
            actual = mixture_moments(
                centers[members], covariances[members], masses[members]
            )
            self.assertAlmostEqual(actual[0], parent_masses[parent], places=12)
            np.testing.assert_allclose(
                actual[1], parent_centers[parent], atol=1e-12
            )
            np.testing.assert_allclose(
                actual[2], parent_covariances[parent], atol=1e-12
            )
        self.assertLess(report["split_local_covariance_relative_error_max"], 1e-12)

    def test_anisotropy_boost_preserves_determinant(self) -> None:
        covariances = np.asarray(
            (np.diag((0.25, 1.0, 4.0)), np.diag((0.5, 0.75, 1.25)))
        )
        boosted = boost_anisotropy(covariances, 1.15, 8.0)
        np.testing.assert_allclose(
            np.linalg.det(boosted), np.linalg.det(covariances), rtol=1e-12
        )

    def test_merge_targets_are_one_to_one(self) -> None:
        coordinates = np.asarray(((0, 0, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0)))
        state, targets = choose_merge_targets(
            coordinates,
            np.asarray((0.0, 3.0, 1.0, 2.0)),
            np.zeros(4, bool),
            np.arange(4),
            (4, 1, 1),
            2,
        )
        removed_targets = targets[state == 1]
        self.assertEqual(len(removed_targets), len(np.unique(removed_targets)))


if __name__ == "__main__":
    unittest.main()
