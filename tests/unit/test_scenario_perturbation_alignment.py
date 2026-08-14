from datetime import UTC, datetime
from pathlib import Path

import pytest

from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
    anchor_perturbation_curve,
    build_perturbation_curve,
)
from synthetic_ops_generator.history.scenario_alignment import (
    align_rollback_perturbation,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

BANK_02_PATH = Path(
    "config/scenarios/banking/BANK-02.yaml"
)

INS_02_PATH = Path(
    "config/scenarios/insurance/INS-02.yaml"
)


def build_timeline():
    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=4,
            plateau_samples=2,
            recovery_samples=4,
        )
    )

    return anchor_perturbation_curve(
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


@pytest.mark.parametrize(
    "scenario_path",
    [
        BANK_02_PATH,
        INS_02_PATH,
    ],
)
def test_real_rollback_scenarios_support_perturbation_alignment(
    scenario_path: Path,
) -> None:
    scenario = load_scenario(
        scenario_path
    )

    alignment = align_rollback_perturbation(
        scenario=scenario,
        timeline=build_timeline(),
    )

    assert (
        alignment.scenario_id
        == scenario.scenario_id
    )


def test_alignment_maps_curve_to_operational_states(
) -> None:
    scenario = load_scenario(
        BANK_02_PATH
    )

    alignment = align_rollback_perturbation(
        scenario=scenario,
        timeline=build_timeline(),
    )

    assert tuple(
        point.operational_state
        for point in alignment.points
    ) == (
        OperationalState.OBSERVING,
        OperationalState.OBSERVING,
        OperationalState.OBSERVING,
        OperationalState.DEGRADED,
        OperationalState.DEGRADED,
        OperationalState.DEGRADED,
        OperationalState.RECOVERY,
        OperationalState.RECOVERY,
        OperationalState.RECOVERY,
        OperationalState.RECOVERY,
    )


def test_alignment_preserves_change_boundary(
) -> None:
    scenario = load_scenario(
        BANK_02_PATH
    )

    alignment = align_rollback_perturbation(
        scenario=scenario,
        timeline=build_timeline(),
    )

    assert (
        alignment.change_boundary_time
        == datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        )
    )

    assert (
        alignment.points[0].timestamp
        > alignment.change_boundary_time
    )


def test_rollback_boundary_occurs_before_recovery_samples(
) -> None:
    scenario = load_scenario(
        BANK_02_PATH
    )

    alignment = align_rollback_perturbation(
        scenario=scenario,
        timeline=build_timeline(),
    )

    assert (
        alignment.rollback_boundary_time
        == datetime(
            2026,
            8,
            14,
            10,
            30,
            tzinfo=UTC,
        )
    )

    recovery_points = tuple(
        point
        for point in alignment.points
        if (
            point.operational_state
            == OperationalState.RECOVERY
        )
    )

    assert all(
        point.timestamp
        > alignment.rollback_boundary_time
        for point in recovery_points
    )

    assert all(
        point.operational_state
        != OperationalState.ROLLBACK
        for point in alignment.points
    )


def test_full_strength_degradation_maps_to_degraded_state(
) -> None:
    scenario = load_scenario(
        BANK_02_PATH
    )

    alignment = align_rollback_perturbation(
        scenario=scenario,
        timeline=build_timeline(),
    )

    peak_points = tuple(
        point
        for point in alignment.points
        if point.strength == 1.0
    )

    assert peak_points

    assert all(
        point.operational_state
        == OperationalState.DEGRADED
        for point in peak_points
    )


def test_rollback_alignment_requires_recovery_phase(
) -> None:
    scenario = load_scenario(
        BANK_02_PATH
    )

    curve = build_perturbation_curve(
        spec=PerturbationCurveSpec(
            degradation_samples=4,
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

    with pytest.raises(
        ValueError,
        match="must contain a recovery phase",
    ):
        align_rollback_perturbation(
            scenario=scenario,
            timeline=timeline,
        )


def test_alignment_rejects_misordered_rollback_scenario(
) -> None:
    scenario = load_scenario(
        BANK_02_PATH
    )

    malformed = scenario.model_copy(
        update={
            "state_sequence": [
                OperationalState.INITIALISING,
                OperationalState.NORMAL,
                OperationalState.IMPLEMENTING,
                OperationalState.DEGRADED,
                OperationalState.OBSERVING,
                OperationalState.ROLLBACK,
                OperationalState.RECOVERY,
                OperationalState.COMPLETED,
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="rollback perturbation state contract",
    ):
        align_rollback_perturbation(
            scenario=malformed,
            timeline=build_timeline(),
        )
