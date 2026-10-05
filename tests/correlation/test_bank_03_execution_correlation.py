import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
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

    generators = GeneratorFactory(
        config_root="config"
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=ids,
        random_source=random_source,
        event_history=runner.event_history,
    )

    visited_states = asyncio.run(
        runner.execute(
            scenario=scenario,
            context=context,
            generators=generators,
            publisher=publisher,
            event_interval_seconds=5,
        )
    )

    report = CrossSourceValidator().validate(
        events=runner.event_history,
        context=context,
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
