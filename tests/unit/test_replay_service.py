from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.replay.service import ReplayService
from synthetic_ops_generator.retention.base import EventStore


class FailingPublisher(EventPublisher):
    def __init__(
        self,
        *,
        fail_on_event_id: str,
    ) -> None:
        self._fail_on_event_id = fail_on_event_id
        self.attempted: list[GeneratedEvent] = []
        self.published: list[GeneratedEvent] = []

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        self.attempted.append(event)

        if event.event_id == self._fail_on_event_id:
            raise RuntimeError(
                "replay destination failed"
            )

        self.published.append(event)


class RecordingEventStore(EventStore):
    def __init__(
        self,
        events: tuple[GeneratedEvent, ...] = (),
    ) -> None:
        self.events = events

    async def start(self) -> None:
        return None

    async def append(
        self,
        event: GeneratedEvent,
    ) -> None:
        raise NotImplementedError

    async def get_run_events(
        self,
        run_id: str,
    ) -> tuple[GeneratedEvent, ...]:
        return tuple(
            event
            for event in self.events
            if event.run_id == run_id
        )

    async def delete_before(
        self,
        cutoff: datetime,
    ) -> int:
        return 0

    async def stop(self) -> None:
        return None


def make_event(
    *,
    event_id: str,
    sequence_number: int,
    run_id: str = "RUN0000001",
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="replay.test",
        event_time=datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_test",
        scenario_id="BANK-01",
        run_id=run_id,
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "message": "replay test",
        },
    )


@pytest.mark.asyncio
async def test_replay_publishes_retained_events_in_order() -> None:
    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
    )

    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
    )

    store = RecordingEventStore(
        events=(
            first,
            second,
        )
    )

    publisher = InMemoryPublisher()

    service = ReplayService(
        store=store,
        publisher=publisher,
    )

    replayed_count = await service.replay_run(
        "RUN0000001"
    )

    assert replayed_count == 2

    assert publisher.events == [
        first,
        second,
    ]


@pytest.mark.asyncio
async def test_replay_preserves_canonical_events() -> None:
    event = make_event(
        event_id="EVT0000001",
        sequence_number=1,
    )

    store = RecordingEventStore(
        events=(event,)
    )

    publisher = InMemoryPublisher()

    service = ReplayService(
        store=store,
        publisher=publisher,
    )

    await service.replay_run(
        "RUN0000001"
    )

    replayed = publisher.events[0]

    assert replayed == event
    assert replayed.event_id == event.event_id
    assert replayed.run_id == event.run_id
    assert replayed.event_time == event.event_time
    assert replayed.sequence_number == event.sequence_number
    assert replayed.data == event.data


@pytest.mark.asyncio
async def test_replay_returns_zero_for_unknown_run() -> None:
    service = ReplayService(
        store=RecordingEventStore(),
        publisher=InMemoryPublisher(),
    )

    replayed_count = await service.replay_run(
        "RUN9999999"
    )

    assert replayed_count == 0


@pytest.mark.asyncio
async def test_replay_rejects_empty_run_id() -> None:
    service = ReplayService(
        store=RecordingEventStore(),
        publisher=InMemoryPublisher(),
    )

    with pytest.raises(
        ValueError,
        match="Run ID is required",
    ):
        await service.replay_run("   ")


@pytest.mark.asyncio
async def test_replay_is_fail_fast_when_publisher_fails() -> None:
    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
    )

    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
    )

    third = make_event(
        event_id="EVT0000003",
        sequence_number=3,
    )

    store = RecordingEventStore(
        events=(
            first,
            second,
            third,
        )
    )

    publisher = FailingPublisher(
        fail_on_event_id="EVT0000002"
    )

    service = ReplayService(
        store=store,
        publisher=publisher,
    )

    with pytest.raises(
        RuntimeError,
        match="replay destination failed",
    ):
        await service.replay_run(
            "RUN0000001"
        )

    assert publisher.attempted == [
        first,
        second,
    ]

    assert publisher.published == [
        first,
    ]