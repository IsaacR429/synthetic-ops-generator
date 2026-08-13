from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.publishers.composite import (
    CompositePublisher,
)
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)


def make_event(
    *,
    event_id: str = "EVT0000001",
    sequence_number: int = 1,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
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
        scenario_id="TEST-PUBLISHER-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "message": "publisher test",
        },
    )


class RecordingPublisher(EventPublisher):
    def __init__(
        self,
        *,
        name: str,
        calls: list[str],
        fail: bool = False,
    ) -> None:
        self.name = name
        self.calls = calls
        self.fail = fail
        self.events: list[GeneratedEvent] = []

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        self.calls.append(self.name)

        if self.fail:
            raise RuntimeError(
                f"{self.name} publication failed"
            )

        self.events.append(event)


@pytest.mark.asyncio
async def test_in_memory_publisher_stores_event() -> None:
    publisher = InMemoryPublisher()
    event = make_event()

    await publisher.publish(event)

    assert publisher.events == [event]
    assert publisher.events[0] is event


@pytest.mark.asyncio
async def test_in_memory_publisher_preserves_order() -> None:
    publisher = InMemoryPublisher()

    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
    )
    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
    )

    await publisher.publish(first)
    await publisher.publish(second)

    assert publisher.events == [
        first,
        second,
    ]


@pytest.mark.asyncio
async def test_in_memory_publisher_clear_removes_events() -> None:
    publisher = InMemoryPublisher()
    event = make_event()

    await publisher.publish(event)

    publisher.clear()

    assert publisher.events == []


@pytest.mark.asyncio
async def test_composite_publisher_forwards_same_event() -> None:
    first = InMemoryPublisher()
    second = InMemoryPublisher()

    publisher = CompositePublisher(
        publishers=(
            first,
            second,
        )
    )

    event = make_event()

    await publisher.publish(event)

    assert first.events == [event]
    assert second.events == [event]

    assert first.events[0] is event
    assert second.events[0] is event


@pytest.mark.asyncio
async def test_composite_publisher_preserves_registration_order() -> None:
    calls: list[str] = []

    first = RecordingPublisher(
        name="first",
        calls=calls,
    )
    second = RecordingPublisher(
        name="second",
        calls=calls,
    )
    third = RecordingPublisher(
        name="third",
        calls=calls,
    )

    publisher = CompositePublisher(
        publishers=(
            first,
            second,
            third,
        )
    )

    await publisher.publish(
        make_event()
    )

    assert calls == [
        "first",
        "second",
        "third",
    ]


def test_composite_publisher_rejects_empty_publishers() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "CompositePublisher requires at least "
            "one publisher"
        ),
    ):
        CompositePublisher(
            publishers=()
        )


@pytest.mark.asyncio
async def test_composite_publisher_propagates_failure() -> None:
    calls: list[str] = []

    first = RecordingPublisher(
        name="first",
        calls=calls,
    )
    failing = RecordingPublisher(
        name="failing",
        calls=calls,
        fail=True,
    )
    third = RecordingPublisher(
        name="third",
        calls=calls,
    )

    publisher = CompositePublisher(
        publishers=(
            first,
            failing,
            third,
        )
    )

    event = make_event()

    with pytest.raises(
        RuntimeError,
        match="failing publication failed",
    ):
        await publisher.publish(event)

    assert calls == [
        "first",
        "failing",
    ]

    assert first.events == [event]
    assert failing.events == []
    assert third.events == []