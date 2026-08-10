from synthetic_ops_generator.domain.enums import OperationalState


class InvalidStateTransition(ValueError):
    pass


_ALLOWED_TRANSITIONS: dict[
    OperationalState,
    set[OperationalState],
] = {
    OperationalState.INITIALISING: {
        OperationalState.NORMAL,
    },

    OperationalState.NORMAL: {
        OperationalState.IMPLEMENTING,
        OperationalState.COMPLETED,
    },

    OperationalState.IMPLEMENTING: {
        OperationalState.OBSERVING,
        OperationalState.FAILURE,
    },

    OperationalState.OBSERVING: {
        OperationalState.WARNING,
        OperationalState.DEGRADED,
        OperationalState.FAILURE,
        OperationalState.COMPLETED,
    },

    OperationalState.WARNING: {
        OperationalState.NORMAL,
        OperationalState.DEGRADED,
        OperationalState.FAILURE,
        OperationalState.COMPLETED,
    },

    OperationalState.DEGRADED: {
        OperationalState.WARNING,
        OperationalState.FAILURE,
        OperationalState.REMEDIATION,
        OperationalState.ROLLBACK,
        OperationalState.RECOVERY,
    },

    OperationalState.FAILURE: {
        OperationalState.REMEDIATION,
        OperationalState.ROLLBACK,
    },

    OperationalState.REMEDIATION: {
        OperationalState.RECOVERY,
        OperationalState.FAILURE,
    },

    OperationalState.ROLLBACK: {
        OperationalState.RECOVERY,
        OperationalState.FAILURE,
    },

    OperationalState.RECOVERY: {
        OperationalState.NORMAL,
        OperationalState.COMPLETED,
    },

    OperationalState.COMPLETED: set(),
}


class ScenarioStateMachine:
    def __init__(
        self,
        initial_state: OperationalState = OperationalState.INITIALISING,
    ) -> None:
        self._state = initial_state

    @property
    def state(self) -> OperationalState:
        return self._state

    def can_transition(self, target: OperationalState) -> bool:
        return target in _ALLOWED_TRANSITIONS[self._state]

    def transition(self, target: OperationalState) -> OperationalState:
        if not self.can_transition(target):
            raise InvalidStateTransition(
                f"Invalid transition: {self._state} -> {target}"
            )

        self._state = target
        return self._state