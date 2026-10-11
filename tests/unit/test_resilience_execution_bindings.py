import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.generators.resilience import (
    ResilienceGenerator,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioResilienceTransition,
)
from synthetic_ops_generator.scenarios.runner import ScenarioRunner


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


def build_resilience_scenario():
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-03.yaml"
    )

    behaviour = ScenarioBehaviour(
        source=SourceDomain.RESILIENCE,
        during_state=scenario.behaviours[0].during_state,
        profile_id="failover_initiated",
        execution_node_id="payment_api_primary",
        resilience_transition=ScenarioResilienceTransition(
            to_execution_node_id="payment_api_secondary"
        ),
    )

    return scenario.model_copy(
        update={
            "behaviours": [
                behaviour,
            ],
        }
    )


def test_resilience_execution_binding_preserves_resolved_peer() -> None:
    enterprise = load_enterprise(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    scenario = build_resilience_scenario()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    assert len(plan.entries) == 1

    entry = plan.entries[0]

    assert entry.execution_target is not None
    assert (
        entry.execution_target.service_instance_id
        == "payment_api_primary"
    )

    assert entry.resilience_transition_target is not None
    assert (
        entry.resilience_transition_target.service_instance_id
        == "payment_api_secondary"
    )

    bindings = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build_execution_bindings(
        scenario=scenario,
        enterprise=enterprise,
        plan=plan,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    assert len(bindings) == 1

    binding = bindings[0]

    assert isinstance(
        binding.generator,
        ResilienceGenerator,
    )

    assert (
        binding.execution_target
        == entry.execution_target
    )
    assert (
        binding.resilience_transition_target
        == entry.resilience_transition_target
    )



class RecordingClock:
    def __init__(self) -> None:
        self._current = datetime(
            2026,
            8,
            15,
            10,
            0,
            tzinfo=UTC,
        )

    def now(self):
        return self._current

    def advance(
        self,
        seconds: float,
    ) -> None:
        self._current += timedelta(
            seconds=seconds
        )


class RecordingPublisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(
        self,
        event,
    ) -> None:
        self.events.append(event)


def test_resilience_binding_executes_from_source_and_records_destination() -> None:
    async def execute() -> None:
        enterprise = load_enterprise(
            CONFIG_ROOT
            / "enterprises"
            / "bank_alpha"
        )
        scenario = build_resilience_scenario()

        # Ensure the bounded runner reaches the behaviour state.
        runtime_behaviour = (
            scenario.behaviours[0].model_copy(
                update={
                    "during_state": (
                        scenario.state_sequence[1]
                    )
                }
            )
        )

        scenario = scenario.model_copy(
            update={
                "behaviours": [
                    runtime_behaviour,
                ],
            }
        )

        plan = build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )

        bindings = GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build_execution_bindings(
            scenario=scenario,
            enterprise=enterprise,
            plan=plan,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
        )

        assert len(bindings) == 1

        binding = bindings[0]

        assert binding.execution_target is not None
        assert (
            binding.execution_target.service_instance_id
            == "payment_api_primary"
        )
        assert (
            binding.resilience_transition_target
            is not None
        )
        assert (
            binding.resilience_transition_target
            .service_instance_id
            == "payment_api_secondary"
        )

        clock = RecordingClock()

        runner = ScenarioRunner(
            ids=IdFactory(),
            clock=clock,
        )

        context = runner.create_context(
            scenario=scenario,
            enterprise=enterprise,
            random_seed=42,
        )

        publisher = RecordingPublisher()

        await runner.execute_bindings(
            scenario=scenario,
            context=context,
            bindings=bindings,
            publisher=publisher,
        )

        resilience_events = [
            event
            for event in publisher.events
            if event.source_domain
            == SourceDomain.RESILIENCE
        ]

        assert len(resilience_events) == 1

        event = resilience_events[0]

        # Envelope describes where the fact was emitted/observed.
        assert event.site_id == "bank_primary"
        assert (
            event.service_instance_id
            == "payment_api_primary"
        )

        observation = event.data[
            "resilience_observation"
        ]

        # Payload describes the factual transition relation.
        assert (
            observation["from_site_id"]
            == "bank_primary"
        )
        assert (
            observation[
                "from_service_instance_id"
            ]
            == "payment_api_primary"
        )
        assert (
            observation["to_site_id"]
            == "bank_secondary"
        )
        assert (
            observation[
                "to_service_instance_id"
            ]
            == "payment_api_secondary"
        )

        # Projected execution must not mutate the base context.
        assert context.site_id is None
        assert context.service_instance_id is None

    asyncio.run(execute())
