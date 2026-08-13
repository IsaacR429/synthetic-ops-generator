from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.composite import CompositePublisher
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.replay.service import ReplayService
from synthetic_ops_generator.retention.sqlite import SQLiteEventStore


def make_event(
    *,
    event_id: str,
    sequence_number: int,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="replay.integration",
        event_time=datetime(
            2026,
            8,
            13,
            10,
            sequence_number,
            tzinfo=UTC,
        ),
        source_system="synthetic_test",
        scenario_id="BANK-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "message": f"event-{sequence_number}",
        },
    )


@pytest.mark.asyncio
async def test_persisted_run_can_be_replayed_after_store_reopen(
    tmp_path,
) -> None:
    database_path = tmp_path / "replay-events.db"

    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
    )

    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
    )

    initial_store = SQLiteEventStore(
        database_path=database_path
    )

    await initial_store.start()

    try:
        await initial_store.append(first)
        await initial_store.append(second)
    finally:
        await initial_store.stop()

    replay_store = SQLiteEventStore(
        database_path=database_path
    )

    first_destination = InMemoryPublisher()
    second_destination = InMemoryPublisher()

    replay_publisher = CompositePublisher(
        [
            first_destination,
            second_destination,
        ]
    )

    replay_service = ReplayService(
        store=replay_store,
        publisher=replay_publisher,
    )

    await replay_store.start()

    try:
        replayed_count = await replay_service.replay_run(
            "RUN0000001"
        )
    finally:
        await replay_store.stop()

    assert replayed_count == 2

    assert first_destination.events == [
        first,
        second,
    ]

    assert second_destination.events == [
        first,
        second,
    ]