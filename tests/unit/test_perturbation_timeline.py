from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
    PerturbationPhase,
    anchor_perturbation_curve,
    build_perturbation_curve,
)


def test_first_perturbation_sample_occurs_after_anchor(
) -> None:
    anchor = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=3,
        )
    )

    timeline = anchor_perturbation_curve(
        curve=curve,
        anchor_time=anchor,
        sample_interval_seconds=300,
    )

    assert timeline.anchor_time == anchor

    assert timeline.points[0].timestamp == datetime(
        2026,
        8,
        14,
        10,
        5,
        tzinfo=UTC,
    )

    assert all(
        point.timestamp != anchor
        for point in timeline.points
    )


def test_perturbation_timestamps_follow_sample_interval(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
            plateau_samples=1,
            recovery_samples=2,
        )
    )

    timeline = anchor_perturbation_curve(
        curve=curve,
        anchor_time=datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        ),
        sample_interval_seconds=300,
    )

    assert tuple(
        point.timestamp
        for point in timeline.points
    ) == (
        datetime(
            2026,
            8,
            14,
            10,
            5,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            8,
            14,
            10,
            10,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            8,
            14,
            10,
            15,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            8,
            14,
            10,
            20,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            8,
            14,
            10,
            25,
            tzinfo=UTC,
        ),
    )


def test_timestamping_preserves_curve_semantics(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
            plateau_samples=1,
            recovery_samples=2,
        )
    )

    timeline = anchor_perturbation_curve(
        curve=curve,
        anchor_time=datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        ),
        sample_interval_seconds=300,
    )

    assert tuple(
        (
            point.sample_index,
            point.phase,
            point.strength,
        )
        for point in timeline.points
    ) == tuple(
        (
            point.sample_index,
            point.phase,
            point.strength,
        )
        for point in curve.points
    )


def test_recovery_finishes_at_expected_time(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=4,
            plateau_samples=2,
            recovery_samples=4,
        )
    )

    timeline = anchor_perturbation_curve(
        curve=curve,
        anchor_time=datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        ),
        sample_interval_seconds=300,
    )

    assert len(timeline.points) == 10

    assert timeline.points[-1].timestamp == datetime(
        2026,
        8,
        14,
        10,
        50,
        tzinfo=UTC,
    )

    assert (
        timeline.points[-1].phase
        == PerturbationPhase.RECOVERY
    )

    assert timeline.points[-1].strength == 0.0


def test_perturbation_timeline_rejects_naive_anchor(
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
        )
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        anchor_perturbation_curve(
            curve=curve,
            anchor_time=datetime(  # noqa: DTZ001
                2026,
                8,
                14,
                10,
                0,
            ),
            sample_interval_seconds=300,
        )


@pytest.mark.parametrize(
    "sample_interval_seconds",
    [
        0,
        -1,
        -300,
    ],
)
def test_perturbation_timeline_rejects_invalid_interval(
    sample_interval_seconds: int,
) -> None:
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=2,
        )
    )

    with pytest.raises(
        ValueError,
        match="greater than zero",
    ):
        anchor_perturbation_curve(
            curve=curve,
            anchor_time=datetime(
                2026,
                8,
                14,
                10,
                0,
                tzinfo=UTC,
            ),
            sample_interval_seconds=(
                sample_interval_seconds
            ),
        )
