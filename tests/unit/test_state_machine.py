import pytest

from synthetic_ops_generator.domain.enums import OperationalState
from synthetic_ops_generator.scenarios.state_machine import (
    InvalidStateTransition,
    ScenarioStateMachine,
)


def test_valid_state_transition() -> None:
    machine = ScenarioStateMachine()

    machine.transition(OperationalState.NORMAL)

    assert machine.state == OperationalState.NORMAL


def test_invalid_state_transition() -> None:
    machine = ScenarioStateMachine()

    with pytest.raises(InvalidStateTransition):
        machine.transition(OperationalState.FAILURE)


def test_normal_can_transition_directly_to_degraded() -> None:
    machine = ScenarioStateMachine()
    machine.transition(
        OperationalState.NORMAL
    )
    machine.transition(
        OperationalState.DEGRADED
    )
    assert machine.state == OperationalState.DEGRADED


def test_normal_can_transition_to_warning() -> None:
    machine = ScenarioStateMachine()
    machine.transition(
        OperationalState.NORMAL
    )
    machine.transition(
        OperationalState.WARNING
    )
    assert machine.state == OperationalState.WARNING
