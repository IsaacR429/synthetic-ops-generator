import pytest

from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
    PerturbationPhase,
    build_perturbation_curve,
)


def test_curve_uses_contiguous_sample_indices(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=3,
            plateau_samples=2,
            recovery_samples=3,
        )
    )

    assert tuple(
        point.sample_index
        for point in curve.points
    ) == tuple(
        range(len(curve.points))
    )


def test_curve_strength_is_always_normalized(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=7,
            plateau_samples=3,
            recovery_samples=7,
        )
    )

    assert all(
        0.0 <= point.strength <= 1.0
        for point in curve.points
    )


def test_recovery_finishes_at_zero_strength(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=3,
            recovery_samples=3,
        )
    )

    assert curve.points[-1].phase == (
        PerturbationPhase.RECOVERY
    )

    assert curve.points[-1].strength == 0.0


def test_curve_without_recovery_finishes_at_peak(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=3,
        )
    )

    assert curve.points[-1].strength == 1.0


@pytest.mark.parametrize(
    (
        "degradation_samples",
        "plateau_samples",
        "recovery_samples",
    ),
    [
        (0, 0, 0),
        (-1, 0, 0),
        (2, -1, 0),
        (2, 0, -1),
    ],
)
def test_curve_rejects_invalid_sample_counts(
    degradation_samples: int,
    plateau_samples: int,
    recovery_samples: int,
) -> None:
    with pytest.raises(ValueError):
        PerturbationCurveSpec(
            degradation_samples=(
                degradation_samples
            ),
            plateau_samples=(
                plateau_samples
            ),
            recovery_samples=(
                recovery_samples
            ),
        )
