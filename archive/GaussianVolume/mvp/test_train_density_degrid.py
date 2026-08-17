"""Minimal regression check for the density de-grid spatial index."""

from train_density_degrid import self_check, trainer_self_check


def test_spatial_index() -> None:
    assert self_check()["status"] == "passed"


def test_trainer_resume() -> None:
    assert trainer_self_check()["status"] == "passed"


if __name__ == "__main__":
    test_spatial_index()
    test_trainer_resume()
    print("train_density_degrid self-check passed")
