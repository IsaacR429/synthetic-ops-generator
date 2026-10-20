import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)

SCENARIO_PATH = Path(
    "config/scenarios/banking/BANK-03.yaml"
)

ENTERPRISE_PATH = Path(
    "config/enterprises/bank_alpha"
)


def test_bank_03_execution_plan_targets_authentication_evidence(
) -> None:
    scenario = load_scenario(SCENARIO_PATH)

    enterprise = load_enterprise_configuration(
        ENTERPRISE_PATH
    )

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    targeted_entries = [
        entry
        for entry in plan.entries
        if entry.execution_target is not None
    ]

    actual_targets = [
        (
            entry.behaviour.source,
            entry.behaviour.profile_id,
            entry.behaviour.during_state.value,
            entry.execution_target.business_stream,
            entry.execution_target.service,
            entry.execution_target.component,
        )
        for entry in targeted_entries
    ]

    assert actual_targets == [
        (
            SourceDomain.LOG,
            "authentication_failure_logs",
            "warning",
            "customer_identity",
            "identity_service",
            "authentication_api",
        ),
        (
            SourceDomain.LOG,
            "authentication_recovery_logs",
            "recovery",
            "customer_identity",
            "identity_service",
            "authentication_api",
        ),
    ]


def test_bank_03_operational_degradation_execution() -> None:
    scenario = load_scenario(SCENARIO_PATH)

    enterprise = load_enterprise_configuration(
        ENTERPRISE_PATH
    )

    ids = IdFactory()

    clock = ManualSimulationClock(
        datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        )
    )

    runner = ScenarioRunner(
        ids=ids,
        clock=clock,
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    random_source = SimulationRandom(
        context.random_seed
    )

    publisher = InMemoryPublisher()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    factory = GeneratorFactory(
        config_root="config"
    )

    bindings = factory.build_execution_bindings(
        scenario=scenario,
        enterprise=enterprise,
        plan=plan,
        ids=ids,
        random_source=random_source,
        event_history=runner.event_history,
    )

    visited_states = asyncio.run(
        runner.execute_bindings(
            scenario=scenario,
            context=context,
            bindings=bindings,
            publisher=publisher,
            event_interval_seconds=5,
        )
    )

    report = CrossSourceValidator().validate(
        events=runner.event_history,
        context=context,
        scenario=scenario,
        execution_plan=plan,
        enterprise=enterprise,
    )

    assert report.is_valid is True
    assert report.findings == []

    assert visited_states == [
        "initialising",
        "normal",
        "warning",
        "degraded",
        "recovery",
        "completed",
    ]

    assert publisher.events

    authentication_failure_events = [
        event
        for event in publisher.events
        if (
            event.event_type == "log.observed"
            and event.business_stream == "customer_identity"
            and event.service == "identity_service"
            and event.component == "authentication_api"
            and event.data["behaviour_profile_id"]
            == "authentication_failure_logs"
        )
    ]

    assert {
        event.data["log"]["log_type"]
        for event in authentication_failure_events
    } == {
        "authentication_failed",
        "authentication_failures_elevated",
        "authentication_service_degraded",
    }

    assert {
        event.data["scenario_state"]
        for event in authentication_failure_events
    } == {"warning"}

    authentication_recovery_events = [
        event
        for event in publisher.events
        if (
            event.event_type == "log.observed"
            and event.business_stream == "customer_identity"
            and event.service == "identity_service"
            and event.component == "authentication_api"
            and event.data["behaviour_profile_id"]
            == "authentication_recovery_logs"
        )
    ]

    assert {
        event.data["log"]["log_type"]
        for event in authentication_recovery_events
    } == {
        "authentication_succeeded",
        "authentication_failures_normalized",
        "authentication_service_recovered",
    }

    assert {
        event.data["scenario_state"]
        for event in authentication_recovery_events
    } == {"recovery"}

    assert {
        event.scenario_id
        for event in publisher.events
    } == {"BANK-03"}

    assert {
        event.run_id
        for event in publisher.events
    } == {context.run_id}

    assert {
        event.chg_id
        for event in publisher.events
    } == {None}

    assert list(
        runner.event_history
    ) == publisher.events

    event_types = {
        event.event_type
        for event in publisher.events
    }

    metric_events = [
        event
        for event in publisher.events
        if event.event_type == "metric.observed"
    ]

    classifications_by_state = {}
    for event in metric_events:
        metric = event.data["metric"]
        classifications_by_state.setdefault(
            metric["scenario_state"],
            set(),
        ).add(
            metric["classification"]
        )

    assert classifications_by_state == {
        "normal": {"normal"},
        "warning": {"warning"},
        "degraded": {"blocking"},
        "recovery": {"normal"},
    }

    payment_blocking_events = [
        event
        for event in metric_events
        if (
            event.service == "payment_service"
            and event.data["metric"]["scenario_state"]
            == "degraded"
            and event.data["metric"]["classification"]
            == "blocking"
        )
    ]

    payment_recovery_events = [
        event
        for event in metric_events
        if (
            event.service == "payment_service"
            and event.data["metric"]["scenario_state"]
            == "recovery"
            and event.data["metric"]["classification"]
            == "normal"
        )
    ]

    payment_dependency_error_events = [
        event
        for event in publisher.events
        if (
            event.event_type == "log.observed"
            and event.business_stream == "payments"
            and event.service == "payment_service"
            and event.component == "payment_api"
            and event.data["behaviour_profile_id"]
            == "degradation_error_logs"
            and event.data["scenario_state"]
            == "degraded"
            and event.data["log"]["error_code"]
            == "DEPENDENCY_ERROR"
        )
    ]

    assert authentication_failure_events
    assert payment_blocking_events
    assert payment_dependency_error_events
    assert authentication_recovery_events
    assert payment_recovery_events

    assert max(
        event.sequence_number
        for event in authentication_failure_events
    ) < min(
        event.sequence_number
        for event in payment_blocking_events
    )

    assert max(
        event.sequence_number
        for event in authentication_recovery_events
    ) < min(
        event.sequence_number
        for event in payment_recovery_events
    )

    assert "metric.observed" in event_types
    assert "itsm.incident.created" in event_types
    assert "itsm.incident.resolved" in event_types

    assert not any(
        event.event_type.startswith(
            "itsm.change."
        )
        for event in publisher.events
    )

    assert not any(
        event.event_type.startswith(
            "cicd."
        )
        for event in publisher.events
    )

    assert [
        event.sequence_number
        for event in publisher.events
    ] == list(
        range(
            1,
            len(publisher.events) + 1,
        )
    )
