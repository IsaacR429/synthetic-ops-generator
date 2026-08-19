from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.retention import (
    RetentionPublisher,
)
from synthetic_ops_generator.retention.base import EventStore
from synthetic_ops_generator.retention.query import (
    EventActivityBucket,
    EventActivityQuery,
    EventQuery,
)


class RecordingEventStore(EventStore):
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.started = False
        self.events: list[GeneratedEvent] = []

    async def start(self) -> None:
        self.started = True

    async def append(
        self,
        event: GeneratedEvent,
    ) -> None:
        if self.fail:
            raise RuntimeError(
                "event store failed"
            )

        self.events.append(event)

    async def get_run_events(
        self,
        run_id: str,
    ) -> tuple[GeneratedEvent, ...]:
        return tuple(
            event
            for event in self.events
            if event.run_id == run_id
        )

    async def query_events(
        self,
        query: EventQuery,
    ) -> tuple[GeneratedEvent, ...]:
        return tuple(
            event
            for event in self.events
            if event.run_id == query.run_id
        )

    async def count_events(
        self,
        query: EventQuery,
    ) -> int:
        return len(
            [
                event
                for event in self.events
                if event.run_id == query.run_id
            ]
        )

    async def aggregate_event_activity(
        self,
        query: EventActivityQuery,
    ) -> tuple[EventActivityBucket, ...]:
        return ()

    async def delete_before(
        self,
        cutoff: datetime,
    ) -> int:
        return 0

    async def stop(self) -> None:
        self.started = False


def make_event() -> GeneratedEvent:
    return GeneratedEvent(
        event_id="EVT0000001",
        event_type="test.event",
        event_time=datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_test",
        scenario_id="TEST-RETENTION-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=1,
        data={
            "message": "retention publisher test",
        },
    )


@pytest.mark.asyncio
async def test_retention_publisher_appends_same_event() -> None:
    store = RecordingEventStore()

    publisher = RetentionPublisher(
        store=store
    )

    event = make_event()

    await publisher.publish(event)

    assert store.events == [event]
    assert store.events[0] is event


@pytest.mark.asyncio
async def test_retention_publisher_propagates_store_failure() -> None:
    store = RecordingEventStore(
        fail=True
    )

    publisher = RetentionPublisher(
        store=store
    )

    with pytest.raises(
        RuntimeError,
        match="event store failed",
    ):
        await publisher.publish(
            make_event()
        )

    assert store.events == []