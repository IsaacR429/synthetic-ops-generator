from collections.abc import (
    Awaitable,
    Callable,
    Sequence,
)
from datetime import datetime

from synthetic_ops_generator.core.clock import SimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enterprise import Enterprise
from synthetic_ops_generator.domain.enums import OperationalState
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import ScenarioDefinition
from synthetic_ops_generator.scenarios.state_machine import ScenarioStateMachine

ScenarioProgressObserver = Callable[
    [OperationalState, int],
    Awaitable[None],
]


class ScenarioRunner:
    """
    Coordinates execution of a validated Scenario definition.

    The runner owns Scenario execution state, Run/Change identifiers,
    and synchronization of ScenarioContext with the simulation clock.

    Source generators do not control Scenario state.
    """

    def __init__(
        self,
        *,
        ids: IdFactory,
        clock: SimulationClock,
    ) -> None:
        self._ids = ids
        self._clock = clock
        self._event_history: list[GeneratedEvent] = []

    def create_context(
        self,
        scenario: ScenarioDefinition,
        enterprise: Enterprise,
        *,
        random_seed: int,
    ) -> ScenarioContext:
        self._validate_enterprise_identity(
            scenario=scenario,
            enterprise=enterprise,
        )

        return ScenarioContext(
            scenario_id=scenario.scenario_id,
            run_id=self._ids.run_id(),
            chg_id=self._ids.change_id(),
            business_stream=scenario.target.business_stream_id,
            service=scenario.target.service_id,
            component=self._default_component(scenario),
            environment=scenario.target.environment,
            risk=scenario.risk,
            scenario_state=scenario.state_sequence[0],
            simulation_time=self._clock.now(),
            random_seed=random_seed,
        )

    def execute_state_sequence(
        self,
        scenario: ScenarioDefinition,
        context: ScenarioContext,
    ) -> list[str]:
        """
        Execute the Scenario's declared state sequence.

        This method changes Scenario state only. Source-system event
        generation is intentionally handled separately.
        """

        state_machine = ScenarioStateMachine(
            initial_state=context.scenario_state,
        )

        visited_states = [state_machine.state.value]

        for target_state in scenario.state_sequence[1:]:
            new_state = state_machine.transition(target_state)

            context.scenario_state = new_state
            context.simulation_time = self._clock.now()

            visited_states.append(new_state.value)

        return visited_states

    async def execute(
        self,
        *,
        scenario: ScenarioDefinition,
        context: ScenarioContext,
        generators: Sequence[SourceGenerator],
        publisher: EventPublisher,
        progress_observer: (
            ScenarioProgressObserver | None
        ) = None,
        event_interval_seconds: float = 5.0,
        stop_at_state: OperationalState | None = None,
    ) -> list[str]:
        """
        Execute a Scenario state sequence and publish events
        produced by registered source generators.
        """

        if event_interval_seconds <= 0:
            raise ValueError(
                "Event interval must be greater than zero."
            )

        if context.scenario_id != scenario.scenario_id:
            raise ValueError(
                "ScenarioContext does not belong to "
                "the supplied Scenario."
            )

        if context.scenario_state != scenario.state_sequence[0]:
            raise ValueError(
                "ScenarioContext must begin in the "
                "Scenario's initial state."
            )

        target_states = scenario.state_sequence[1:]

        if stop_at_state is not None:
            try:
                stop_index = scenario.state_sequence.index(
                    stop_at_state
                )
            except ValueError as exc:
                raise ValueError(
                    "Requested stop state is not part "
                    "of the Scenario state sequence."
                ) from exc

            if stop_index == 0:
                raise ValueError(
                    "Scenario execution cannot stop "
                    "at the initial state."
                )

            target_states = (
                scenario.state_sequence[
                    1 : stop_index + 1
                ]
            )

        self._event_history.clear()

        state_machine = ScenarioStateMachine(
            initial_state=context.scenario_state,
        )

        visited_states = [
            state_machine.state.value
        ]

        for target_state in target_states:
            new_state = state_machine.transition(
                target_state
            )

            context.scenario_state = new_state
            context.simulation_time = self._clock.now()

            visited_states.append(
                new_state.value
            )

            if progress_observer is not None:
                await progress_observer(
                    context.scenario_state,
                    len(self._event_history),
                )

            for generator in generators:
                async for event in generator.generate(
                    context
                ):
                    await publisher.publish(event)

                    self._event_history.append(event)

                    self._clock.advance(
                        event_interval_seconds
                    )

                    context.simulation_time = (
                        self._clock.now()
                    )

            if progress_observer is not None:
                await progress_observer(
                    context.scenario_state,
                    len(self._event_history),
                )

        return visited_states

    @staticmethod
    def _default_component(
        scenario: ScenarioDefinition,
    ) -> str | None:
        if not scenario.target.component_ids:
            return None

        return scenario.target.component_ids[0]

    @staticmethod
    def _validate_enterprise_identity(
        *,
        scenario: ScenarioDefinition,
        enterprise: Enterprise,
    ) -> None:
        if scenario.target.enterprise_id != enterprise.enterprise_id:
            raise ValueError(
                "Scenario target enterprise does not match "
                "the supplied Enterprise."
            )

    @property
    def current_time(self) -> datetime:
        return self._clock.now()

    @property
    def event_history(
        self,
    ) -> Sequence[GeneratedEvent]:
        return self._event_history