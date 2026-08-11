import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import SourceDomain
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)

SCENARIO_PATH = Path(
    "config/scenarios/banking/BANK-01.yaml"
)

ENTERPRISE_PATH = Path(
    "config/enterprises/bank_alpha"
)


def test_bank_01_itsm_and_deployment_execution() -> None:
    scenario = load_scenario(SCENARIO_PATH)

    enterprise = load_enterprise_configuration(
        ENTERPRISE_PATH
    )

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )

    service = next(
        service
        for service in enterprise.services
        if service.service_id == scenario.target.service_id
    )

    itsm_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.ITSM
    )

    deployment_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.DEPLOYMENT
    )

    assert scenario.trigger.artifact is not None
    assert scenario.trigger.version is not None

    ids = IdFactory()

    clock = ManualSimulationClock(
        datetime(
            2026,
            8,
            11,
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

    publisher = InMemoryPublisher()

    generators = [
        ITSMGenerator(
            ids=ids,
            behaviour=itsm_behaviour,
            service_owner=service.owner,
            component_ids=scenario.target.component_ids,
        ),
        DeploymentGenerator(
            ids=ids,
            behaviour=deployment_behaviour,
            artifact=scenario.trigger.artifact,
            artifact_version=scenario.trigger.version,
        ),
    ]

    visited_states = asyncio.run(
        runner.execute(
            scenario=scenario,
            context=context,
            generators=generators,
            publisher=publisher,
            event_interval_seconds=5,
        )
    )

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert len(publisher.events) == 5

    assert [
        event.event_type
        for event in publisher.events
    ] == [
        "itsm.change.created",
        "itsm.approval.approved",
        "cicd.deployment.created",
        "cicd.deployment.started",
        "cicd.deployment.completed",
    ]

    assert {
        event.scenario_id
        for event in publisher.events
    } == {"BANK-01"}

    assert {
        event.run_id
        for event in publisher.events
    } == {context.run_id}

    assert {
        event.chg_id
        for event in publisher.events
    } == {context.chg_id}

    assert {
        event.business_stream
        for event in publisher.events
    } == {"payments"}

    assert {
        event.service
        for event in publisher.events
    } == {"payment_service"}

    assert [
        event.sequence_number
        for event in publisher.events
    ] == [1, 2, 3, 4, 5]

    event_times = [
        event.event_time
        for event in publisher.events
    ]

    assert event_times == sorted(event_times)

    assert len(set(event_times)) == 5

    assert context.deployment_id == "DEP0000001"
    assert context.scenario_state.value == "completed"