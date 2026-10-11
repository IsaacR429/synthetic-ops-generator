from datetime import UTC, datetime
from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.log import LogGenerator
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionState,
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    ScenarioExecutionPlan,
    ScenarioExecutionPlanEntry,
)
from synthetic_ops_generator.scenarios.execution_target import (
    resolve_scenario_execution_target,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    NORMAL_OPERATIONAL_LOGS,
)
from synthetic_ops_generator.topology.resolver import (
    TopologyResolver,
)
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"

BASE_TIME = datetime(
    2026,
    10,
    8,
    20,
    0,
    tzinfo=UTC,
)


def load_bank_alpha():
    return load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )


def build_execution_state() -> ScenarioExecutionState:
    return ScenarioExecutionState(
        scenario_id="E5-TEST",
        run_id="RUN0000001",
        chg_id=None,
        risk=RiskLevel.HIGH,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_secondary_target() -> ScenarioExecutionTarget:
    return ScenarioExecutionTarget(
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )


def build_context(
    target: ScenarioExecutionTarget | None = None,
) -> ScenarioContext:
    return ScenarioContext(
        execution_state=build_execution_state(),
        target=(
            target
            if target is not None
            else ScenarioExecutionTarget(
                business_stream="payments",
                service="payment_service",
                component="payment_api",
                environment=Environment.PRODUCTION,
            )
        ),
    )


def test_service_instance_resolves_to_execution_identity() -> None:
    enterprise = load_bank_alpha()
    topology = TopologyResolver(enterprise)

    target = resolve_scenario_execution_target(
        topology=topology,
        node_id="payment_api_secondary",
        environment=Environment.PRODUCTION,
    )

    assert target.business_stream == "payments"
    assert target.service == "payment_service"
    assert target.component == "payment_api"
    assert target.environment == Environment.PRODUCTION

    assert target.site_id == "bank_secondary"
    assert (
        target.service_instance_id
        == "payment_api_secondary"
    )


def test_context_projects_service_instance_identity() -> None:
    target = build_secondary_target()
    context = build_context(target)

    assert context.business_stream == "payments"
    assert context.service == "payment_service"
    assert context.component == "payment_api"
    assert context.environment == Environment.PRODUCTION

    assert context.site_id == "bank_secondary"
    assert (
        context.service_instance_id
        == "payment_api_secondary"
    )

    projected = context.for_target(
        ScenarioExecutionTarget(
            business_stream="payments",
            service="payment_service",
            component="payment_api",
            environment=Environment.PRODUCTION,
            site_id="bank_primary",
            service_instance_id="payment_api_primary",
        )
    )

    assert projected.execution_state is context.execution_state
    assert projected.site_id == "bank_primary"
    assert (
        projected.service_instance_id
        == "payment_api_primary"
    )

    assert context.site_id == "bank_secondary"
    assert (
        context.service_instance_id
        == "payment_api_secondary"
    )


@pytest.mark.asyncio
async def test_targeted_log_event_preserves_instance_lineage() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id=NORMAL_OPERATIONAL_LOGS,
    )

    generator = LogGenerator(
        ids=IdFactory(),
        behaviour=behaviour,
        random_source=SimulationRandom(42),
    )

    context = build_context(
        build_secondary_target()
    )

    events = [
        event
        async for event in generator.generate(context)
    ]

    assert events

    assert all(
        event.service == "payment_service"
        for event in events
    )

    assert all(
        event.site_id == "bank_secondary"
        for event in events
    )

    assert all(
        event.service_instance_id
        == "payment_api_secondary"
        for event in events
    )


def test_execution_scope_distinguishes_primary_and_secondary_instances(
) -> None:
    enterprise = load_bank_alpha()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id=NORMAL_OPERATIONAL_LOGS,
    )

    secondary_target = build_secondary_target()

    execution_plan = ScenarioExecutionPlan(
        entries=(
            ScenarioExecutionPlanEntry(
                behaviour=behaviour,
                execution_target=secondary_target,
            ),
        )
    )

    event = GeneratedEvent(
        event_id="EVT0000001",
        event_type="log.observed",
        event_time=BASE_TIME,
        source_system="synthetic_log",
        source_domain=SourceDomain.LOG,
        scenario_id="E5-TEST",
        run_id="RUN0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        sequence_number=1,
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
        execution_plan=execution_plan,
    )

    assert report.is_valid is False

    assert "execution_target_scope" in {
        finding.rule
        for finding in report.findings
    }
def test_execution_scope_accepts_authorized_secondary_instance(
) -> None:
    enterprise = load_bank_alpha()

    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id=NORMAL_OPERATIONAL_LOGS,
    )

    secondary_target = build_secondary_target()

    execution_plan = ScenarioExecutionPlan(
        entries=(
            ScenarioExecutionPlanEntry(
                behaviour=behaviour,
                execution_target=secondary_target,
            ),
        )
    )

    event = GeneratedEvent(
        event_id="EVT0000002",
        event_type="log.observed",
        event_time=BASE_TIME,
        source_system="synthetic_log",
        source_domain=SourceDomain.LOG,
        scenario_id="E5-TEST",
        run_id="RUN0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
        sequence_number=1,
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
        execution_plan=execution_plan,
    )

    assert report.is_valid is True
    assert report.findings == []


def _e54b_event(
    *,
    event_id: str = "EVT-E54B-001",
    business_stream: str = "payments",
    service: str = "payment_service",
    component: str | None = "payment_api",
    environment: Environment = Environment.PRODUCTION,
    site_id: str | None = "bank_secondary",
    service_instance_id: str | None = "payment_api_secondary",
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="log.observed",
        event_time=BASE_TIME,
        source_system="synthetic_log",
        source_domain=SourceDomain.LOG,
        scenario_id="E5-TEST",
        run_id="RUN0000001",
        business_stream=business_stream,
        service=service,
        component=component,
        environment=environment,
        site_id=site_id,
        service_instance_id=service_instance_id,
        sequence_number=1,
    )


def _e54b_validate(
    event: GeneratedEvent,
):
    target = ScenarioExecutionTarget(
        business_stream=event.business_stream,
        service=event.service,
        component=event.component,
        environment=event.environment,
        site_id=event.site_id,
        service_instance_id=event.service_instance_id,
    )

    return CrossSourceValidator().validate(
        events=[event],
        context=build_context(target),
        enterprise=load_bank_alpha(),
    )


def _e54b_rules(report) -> set[str]:
    return {
        finding.rule
        for finding in report.findings
    }


def test_e54b_generic_event_without_placement_remains_valid(
) -> None:
    event = _e54b_event(
        site_id=None,
        service_instance_id=None,
    )

    report = _e54b_validate(event)

    assert report.is_valid is True
    assert report.findings == []


def test_e54b_known_site_only_event_is_valid(
) -> None:
    event = _e54b_event(
        site_id="bank_secondary",
        service_instance_id=None,
    )

    report = _e54b_validate(event)

    assert report.is_valid is True
    assert report.findings == []


def test_e54b_valid_service_instance_identity_is_valid(
) -> None:
    event = _e54b_event()

    report = _e54b_validate(event)

    assert report.is_valid is True
    assert report.findings == []


def test_e54b_unknown_site_is_reported(
) -> None:
    event = _e54b_event(
        site_id="ghost_site",
        service_instance_id=None,
    )

    report = _e54b_validate(event)

    assert "site_reference" in _e54b_rules(report)


def test_e54b_unknown_service_instance_is_reported(
) -> None:
    event = _e54b_event(
        service_instance_id="ghost_instance",
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_reference"
        in _e54b_rules(report)
    )


def test_e54b_service_instance_requires_site_identity(
) -> None:
    event = _e54b_event(
        site_id=None,
        service_instance_id="payment_api_secondary",
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_site_relationship"
        in _e54b_rules(report)
    )


def test_e54b_service_instance_site_mismatch_is_reported(
) -> None:
    event = _e54b_event(
        site_id="bank_primary",
        service_instance_id="payment_api_secondary",
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_site_relationship"
        in _e54b_rules(report)
    )


def test_e54b_service_instance_service_mismatch_is_reported(
) -> None:
    event = _e54b_event(
        business_stream="accounts",
        service="account_service",
        component="account_database",
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_service_relationship"
        in _e54b_rules(report)
    )


def test_e54b_service_instance_component_mismatch_is_reported(
) -> None:
    event = _e54b_event(
        component="account_database",
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_component_relationship"
        in _e54b_rules(report)
    )


def test_e54b_service_instance_environment_mismatch_is_reported(
) -> None:
    event = _e54b_event(
        environment=Environment.TEST,
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_environment_relationship"
        in _e54b_rules(report)
    )


def test_execution_scope_accepts_instance_identity_from_context_without_plan(
) -> None:
    enterprise = load_bank_alpha()

    event = GeneratedEvent(
        event_id="EVT-E54B-PRE-001",
        event_type="log.observed",
        event_time=BASE_TIME,
        source_system="synthetic_log",
        source_domain=SourceDomain.LOG,
        scenario_id="E5-TEST",
        run_id="RUN0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
        sequence_number=1,
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(
            build_secondary_target()
        ),
        enterprise=enterprise,
    )

    assert "execution_target_scope" not in {
        finding.rule
        for finding in report.findings
    }


def _e55_primary_target() -> ScenarioExecutionTarget:
    enterprise = load_bank_alpha()
    topology = TopologyResolver(enterprise)

    return resolve_scenario_execution_target(
        topology=topology,
        node_id="payment_api_primary",
        environment=Environment.PRODUCTION,
    )


def _e55_secondary_target() -> ScenarioExecutionTarget:
    enterprise = load_bank_alpha()
    topology = TopologyResolver(enterprise)

    return resolve_scenario_execution_target(
        topology=topology,
        node_id="payment_api_secondary",
        environment=Environment.PRODUCTION,
    )


def test_e55_primary_secondary_instances_resolve_independently(
) -> None:
    primary = _e55_primary_target()
    secondary = _e55_secondary_target()

    assert primary.business_stream == secondary.business_stream
    assert primary.service == secondary.service
    assert primary.component == secondary.component
    assert primary.environment == secondary.environment

    assert primary.site_id == "bank_primary"
    assert secondary.site_id == "bank_secondary"

    assert primary.service_instance_id == "payment_api_primary"
    assert (
        secondary.service_instance_id
        == "payment_api_secondary"
    )

    assert primary != secondary


@pytest.mark.asyncio
async def test_e55_primary_secondary_log_generation_shares_run_state_without_identity_bleed(
) -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id=NORMAL_OPERATIONAL_LOGS,
    )

    ids = IdFactory()

    primary_generator = LogGenerator(
        ids=ids,
        behaviour=behaviour,
        random_source=SimulationRandom(42),
    )

    secondary_generator = LogGenerator(
        ids=ids,
        behaviour=behaviour,
        random_source=SimulationRandom(43),
    )

    primary_context = build_context(
        _e55_primary_target()
    )

    secondary_context = primary_context.for_target(
        _e55_secondary_target()
    )

    assert (
        primary_context.execution_state
        is secondary_context.execution_state
    )

    primary_events = [
        event
        async for event in primary_generator.generate(
            primary_context
        )
    ]

    secondary_events = [
        event
        async for event in secondary_generator.generate(
            secondary_context
        )
    ]

    assert primary_events
    assert secondary_events

    all_events = primary_events + secondary_events

    assert {
        event.run_id
        for event in all_events
    } == {"RUN0000001"}

    assert {
        event.scenario_id
        for event in all_events
    } == {"E5-TEST"}

    sequences = [
        event.sequence_number
        for event in all_events
    ]

    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))

    assert max(
        event.sequence_number
        for event in primary_events
    ) < min(
        event.sequence_number
        for event in secondary_events
    )

    assert {
        event.site_id
        for event in primary_events
    } == {"bank_primary"}

    assert {
        event.service_instance_id
        for event in primary_events
    } == {"payment_api_primary"}

    assert {
        event.site_id
        for event in secondary_events
    } == {"bank_secondary"}

    assert {
        event.service_instance_id
        for event in secondary_events
    } == {"payment_api_secondary"}

    assert primary_context.site_id == "bank_primary"
    assert (
        primary_context.service_instance_id
        == "payment_api_primary"
    )

    assert secondary_context.site_id == "bank_secondary"
    assert (
        secondary_context.service_instance_id
        == "payment_api_secondary"
    )


@pytest.mark.asyncio
async def test_e55_runner_preserves_primary_secondary_binding_identity_and_shared_sequence(
) -> None:
    from synthetic_ops_generator.config.enterprise_loader import (
        load_enterprise_configuration,
    )
    from synthetic_ops_generator.core.clock import (
        ManualSimulationClock,
    )
    from synthetic_ops_generator.events.envelope import (
        GeneratedEvent,
    )
    from synthetic_ops_generator.generators.bindings import (
        SourceExecutionBinding,
    )
    from synthetic_ops_generator.publishers.memory import (
        InMemoryPublisher,
    )
    from synthetic_ops_generator.scenarios.loader import (
        load_scenario,
    )
    from synthetic_ops_generator.scenarios.runner import (
        ScenarioRunner,
    )

    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )

    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )

    primary_target = _e55_primary_target()
    secondary_target = _e55_secondary_target()

    behaviour = scenario.behaviours[0]

    class InstanceRecordingGenerator:
        source_system = "e55_instance_recorder"

        async def generate(
            self,
            context: ScenarioContext,
        ):
            sequence_number = context.next_sequence()

            yield GeneratedEvent(
                event_id=(
                    f"EVT-E55-{sequence_number:03d}"
                ),
                event_type="e55.instance.observed",
                event_time=context.simulation_time,
                source_system=self.source_system,
                source_domain=behaviour.source,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=context.component,
                environment=context.environment,
                site_id=context.site_id,
                service_instance_id=(
                    context.service_instance_id
                ),
                sequence_number=sequence_number,
            )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(BASE_TIME),
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    bindings = [
        SourceExecutionBinding(
            behaviour=behaviour,
            generator=InstanceRecordingGenerator(),
            execution_target=primary_target,
        ),
        SourceExecutionBinding(
            behaviour=behaviour,
            generator=InstanceRecordingGenerator(),
            execution_target=secondary_target,
        ),
    ]

    publisher = InMemoryPublisher()

    await runner.execute_bindings(
        scenario=scenario,
        context=context,
        bindings=bindings,
        publisher=publisher,
        stop_at_state=behaviour.during_state,
    )

    events = publisher.events

    assert len(events) == 2

    primary_event, secondary_event = events

    assert primary_event.run_id == secondary_event.run_id
    assert (
        primary_event.scenario_id
        == secondary_event.scenario_id
    )

    assert [
        primary_event.sequence_number,
        secondary_event.sequence_number,
    ] == [1, 2]

    assert (
        primary_event.site_id,
        primary_event.service_instance_id,
    ) == (
        "bank_primary",
        "payment_api_primary",
    )

    assert (
        secondary_event.site_id,
        secondary_event.service_instance_id,
    ) == (
        "bank_secondary",
        "payment_api_secondary",
    )

    assert (
        primary_event.service
        == secondary_event.service
        == "payment_service"
    )

    assert (
        primary_event.component
        == secondary_event.component
        == "payment_api"
    )


def test_e55_canonical_serialization_preserves_placement_identity(
) -> None:
    from synthetic_ops_generator.events.serialization import (
        deserialize_generated_event,
        serialize_generated_event,
    )

    event = _e54b_event(
        event_id="EVT-E55-SERIALIZED",
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )

    payload = serialize_generated_event(event)
    restored = deserialize_generated_event(payload)

    assert restored == event

    assert restored.site_id == "bank_secondary"
    assert (
        restored.service_instance_id
        == "payment_api_secondary"
    )

    assert serialize_generated_event(restored) == payload


def test_e55_generic_event_remains_placement_free_after_serialization(
) -> None:
    from synthetic_ops_generator.events.serialization import (
        deserialize_generated_event,
        serialize_generated_event,
    )

    event = _e54b_event(
        event_id="EVT-E55-GENERIC",
        site_id=None,
        service_instance_id=None,
    )

    restored = deserialize_generated_event(
        serialize_generated_event(event)
    )

    assert restored == event
    assert restored.site_id is None
    assert restored.service_instance_id is None


def test_e56_component_bound_instance_allows_service_scoped_event(
) -> None:
    event = _e54b_event(
        component=None,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )

    report = _e54b_validate(event)

    assert (
        "service_instance_component_relationship"
        not in _e54b_rules(report)
    )

    assert report.is_valid is True
    assert report.findings == []
