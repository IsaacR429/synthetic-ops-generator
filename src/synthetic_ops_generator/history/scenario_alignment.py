from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationPhase,
    TimestampedPerturbationCurve,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
)

_REQUIRED_ROLLBACK_STATES = (
    OperationalState.OBSERVING,
    OperationalState.DEGRADED,
    OperationalState.ROLLBACK,
    OperationalState.RECOVERY,
)


@dataclass(frozen=True)
class ScenarioPerturbationPoint:
    sample_index: int
    timestamp: datetime
    phase: PerturbationPhase
    strength: float
    operational_state: OperationalState


@dataclass(frozen=True)
class ScenarioPerturbationAlignment:
    scenario_id: str
    change_boundary_time: datetime
    rollback_boundary_time: datetime
    points: tuple[
        ScenarioPerturbationPoint,
        ...,
    ]


def align_rollback_perturbation(
    *,
    scenario: ScenarioDefinition,
    timeline: TimestampedPerturbationCurve,
) -> ScenarioPerturbationAlignment:
    _validate_rollback_state_sequence(scenario)

    if not timeline.points:
        raise ValueError(
            "Perturbation timeline must contain points."
        )

    recovery_start_index = next(
        (
            index
            for index, point in enumerate(timeline.points)
            if point.phase == PerturbationPhase.RECOVERY
        ),
        None,
    )

    if recovery_start_index is None:
        raise ValueError(
            "Rollback perturbation timeline must contain a recovery phase."
        )

    if recovery_start_index == 0:
        raise ValueError(
            "Rollback perturbation recovery cannot begin before degradation."
        )

    rollback_boundary_time = (
        timeline.points[
            recovery_start_index - 1
        ].timestamp
    )

    aligned_points = tuple(
        ScenarioPerturbationPoint(
            sample_index=point.sample_index,
            timestamp=point.timestamp,
            phase=point.phase,
            strength=point.strength,
            operational_state=(
                _state_for_perturbation_point(
                    phase=point.phase,
                    strength=point.strength,
                )
            ),
        )
        for point in timeline.points
    )

    return ScenarioPerturbationAlignment(
        scenario_id=scenario.scenario_id,
        change_boundary_time=(
            timeline.anchor_time
        ),
        rollback_boundary_time=(
            rollback_boundary_time
        ),
        points=aligned_points,
    )


def _state_for_perturbation_point(
    *,
    phase: PerturbationPhase,
    strength: float,
) -> OperationalState:
    if phase == PerturbationPhase.DEGRADATION:
        if strength >= 1.0:
            return OperationalState.DEGRADED

        return OperationalState.OBSERVING

    if phase == PerturbationPhase.PLATEAU:
        return OperationalState.DEGRADED

    if phase == PerturbationPhase.RECOVERY:
        return OperationalState.RECOVERY

    raise ValueError(
        f"Unsupported perturbation phase: {phase}"
    )


def _validate_rollback_state_sequence(
    scenario: ScenarioDefinition,
) -> None:
    next_search_index = 0

    for required_state in (
        _REQUIRED_ROLLBACK_STATES
    ):
        try:
            state_index = (
                scenario.state_sequence.index(
                    required_state,
                    next_search_index,
                )
            )
        except ValueError as exc:
            raise ValueError(
                "Scenario does not satisfy "
                "the rollback perturbation "
                "state contract. Missing or "
                "misordered state: "
                f"{required_state.value}"
            ) from exc

        next_search_index = (
            state_index + 1
        )
