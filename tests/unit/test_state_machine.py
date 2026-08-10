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