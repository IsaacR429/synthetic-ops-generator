from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    deserialize_generated_event,
    serialize_generated_event,
)
from synthetic_ops_generator.publishers.streaming import (
    StreamingPublisher,
)
from synthetic_ops_generator.streaming.base import StreamTransport


class RecordingStreamTransport(StreamTransport):
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.messages: list[
            tuple[str, bytes, bytes]
        ] = []

    async def start(self) -> None:
        return None

    async def send(
        self,
        *,
        topic: str,
        key: bytes,
        value: bytes,
    ) -> None:
        if self.fail:
            raise RuntimeError(
                "stream transport failed"
            )

        self.messages.append(
            (
                topic,
                key,
                value,
            )
        )

    async def stop(self) -> None:
        return None


def make_event(
    *,
    event_id: str = "EVT0000001",
    run_id: str = "RUN0000001",
    sequence_number: int = 1,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="metric.observed",
        event_time=datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_observability",
        scenario_id="BANK-01",
        run_id=run_id,
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "metric": {
                "metric_id": "request_latency",
                "value": 180.5,
            }
        },
    )


def test_streaming_publisher_rejects_empty_topic() -> None:
    transport = RecordingStreamTransport()

    with pytest.raises(
        ValueError,
        match="StreamingPublisher requires a topic",
    ):
        StreamingPublisher(
            transport=transport,
            topic="   ",
        )


@pytest.mark.asyncio
async def test_streaming_publisher_uses_configured_topic() -> None:
    transport = RecordingStreamTransport()

    publisher = StreamingPublisher(
        transport=transport,
        topic="synthetic.operational.events",
    )

    await publisher.publish(
        make_event()
    )

    assert len(transport.messages) == 1

    topic, _, _ = transport.messages[0]

    assert (
        topic
        == "synthetic.operational.events"
    )


@pytest.mark.asyncio
async def test_streaming_publisher_uses_run_id_as_key() -> None:
    transport = RecordingStreamTransport()

    publisher = StreamingPublisher(
        transport=transport,
        topic="synthetic.operational.events",
    )

    event = make_event(
        run_id="RUN0000042"
    )

    await publisher.publish(event)

    _, key, _ = transport.messages[0]

    assert key == b"RUN0000042"


@pytest.mark.asyncio
async def test_streaming_publisher_uses_canonical_serialization() -> None:
    transport = RecordingStreamTransport()

    publisher = StreamingPublisher(
        transport=transport,
        topic="synthetic.operational.events",
    )

    event = make_event()

    await publisher.publish(event)

    _, _, value = transport.messages[0]

    assert value == serialize_generated_event(
        event
    )

    assert (
        deserialize_generated_event(value)
        == event
    )


@pytest.mark.asyncio
async def test_streaming_publisher_preserves_publish_order() -> None:
    transport = RecordingStreamTransport()

    publisher = StreamingPublisher(
        transport=transport,
        topic="synthetic.operational.events",
    )

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

    restored = [
        deserialize_generated_event(value)
        for _, _, value in transport.messages
    ]

    assert restored == [
        first,
        second,
    ]


@pytest.mark.asyncio
async def test_streaming_publisher_propagates_transport_failure() -> None:
    transport = RecordingStreamTransport(
        fail=True
    )

    publisher = StreamingPublisher(
        transport=transport,
        topic="synthetic.operational.events",
    )

    with pytest.raises(
        RuntimeError,
        match="stream transport failed",
    ):
        await publisher.publish(
            make_event()
        )

    assert transport.messages == []
