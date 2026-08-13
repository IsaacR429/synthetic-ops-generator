from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.composite import CompositePublisher
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.publishers.retention import RetentionPublisher
from synthetic_ops_generator.retention.sqlite import SQLiteEventStore
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from tests.unit.test_scenario_runner import (
    build_enterprise,
    build_scenario,
)


class AcceptanceGenerator:
    def __init__(self) -> None:
        self._sequence_number = 0

    async def generate(
        self,
        context: ScenarioContext,
    ):
        self._sequence_number += 1

        yield GeneratedEvent(
            event_id=f"EVT{self._sequence_number:07d}",
            event_type="acceptance.event",
            event_time=context.simulation_time,
            source_system="synthetic_acceptance",
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            sequence_number=self._sequence_number,
            data={
                "scenario_state": context.scenario_state.value,
            },
        )


@pytest.mark.asyncio
async def test_scenario_events_are_retained_and_restored(
    tmp_path,
) -> None:
    database_path = tmp_path / "retained-events.db"

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(
            datetime(
                2026,
                8,
                13,
                10,
                0,
                tzinfo=UTC,
            )
        ),
    )

    scenario = build_scenario()

    context = runner.create_context(
        scenario=scenario,
        enterprise=build_enterprise(),
        random_seed=42,
    )

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    memory_publisher = InMemoryPublisher()

    retention_publisher = RetentionPublisher(
        store=store
    )

    publisher = CompositePublisher(
        [
            memory_publisher,
            retention_publisher,
        ]
    )

    try:
        visited_states = await runner.execute(
            scenario=scenario,
            context=context,
            generators=[
                AcceptanceGenerator()
            ],
            publisher=publisher,
        )
    finally:
        await store.stop()

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert list(runner.event_history) == (
        memory_publisher.events
    )

    assert len(runner.event_history) == 4

    reopened_store = SQLiteEventStore(
        database_path=database_path
    )

    await reopened_store.start()

    try:
        restored_events = (
            await reopened_store.get_run_events(
                context.run_id
            )
        )
    finally:
        await reopened_store.stop()

    assert restored_events == tuple(
        runner.event_history
    )

    assert [
        event.sequence_number
        for event in restored_events
    ] == [
        1,
        2,
        3,
        4,
    ]