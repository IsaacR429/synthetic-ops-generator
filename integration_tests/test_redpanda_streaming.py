import asyncio
import os
from datetime import UTC, datetime

import pytest
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    deserialize_generated_event,
)
from synthetic_ops_generator.publishers.streaming import (
    StreamingPublisher,
)
from synthetic_ops_generator.streaming.kafka import (
    KafkaStreamTransport,
)

TOPIC = "synthetic.operational.events"

BOOTSTRAP_SERVERS = os.getenv(
    "SYNTHETIC_OPS_KAFKA_BOOTSTRAP_SERVERS",
)


def make_event(
    *,
    event_id: str,
    sequence_number: int,
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
        run_id="RUN0000001",
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


@pytest.mark.asyncio
async def test_generated_events_round_trip_through_redpanda() -> None:
    if BOOTSTRAP_SERVERS is None:
        pytest.skip(
            "Redpanda integration environment is not configured."
        )

    transport = KafkaStreamTransport(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        client_id="synthetic-ops-integration-producer",
    )

    publisher = StreamingPublisher(
        transport=transport,
        topic=TOPIC,
    )

    consumer = AIOKafkaConsumer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        client_id="synthetic-ops-integration-consumer",
        enable_auto_commit=False,
    )

    first = make_event(
        event_id="EVT9000001",
        sequence_number=1,
    )

    second = make_event(
        event_id="EVT9000002",
        sequence_number=2,
    )

    await consumer.start()

    try:
        partitions = [
            TopicPartition(
                TOPIC,
                partition_number,
            )
            for partition_number in range(3)
        ]

        consumer.assign(partitions)

        await consumer.seek_to_end(
            *partitions
        )

        await transport.start()

        try:
            await publisher.publish(first)
            await publisher.publish(second)

            first_record = await asyncio.wait_for(
                consumer.getone(),
                timeout=10.0,
            )

            second_record = await asyncio.wait_for(
                consumer.getone(),
                timeout=10.0,
            )

        finally:
            await transport.stop()

    finally:
        await consumer.stop()

    assert first_record.topic == TOPIC
    assert second_record.topic == TOPIC

    assert first_record.key == b"RUN0000001"
    assert second_record.key == b"RUN0000001"

    assert (
        first_record.partition
        == second_record.partition
    )

    assert (
        first_record.offset
        < second_record.offset
    )

    restored_first = deserialize_generated_event(
        first_record.value
    )

    restored_second = deserialize_generated_event(
        second_record.value
    )

    assert restored_first == first
    assert restored_second == second