from synthetic_ops_generator.metrics.perturbation import (
    PerturbationCurveSpec,
    PerturbationPhase,
    build_perturbation_curve,
)


def test_shared_metric_perturbation_builds_degradation_curve() -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=4,
        )
    )

    assert [
        point.phase
        for point in curve.points
    ] == [
        PerturbationPhase.DEGRADATION,
        PerturbationPhase.DEGRADATION,
        PerturbationPhase.DEGRADATION,
        PerturbationPhase.DEGRADATION,
    ]

    assert [
        point.strength
        for point in curve.points
    ] == [
        0.25,
        0.50,
        0.75,
        1.0,
    ]
