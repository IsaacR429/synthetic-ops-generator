import asyncio
import os
from contextlib import suppress
from datetime import UTC, datetime

import pytest
from aiokafka import AIOKafkaConsumer
from aiokafka.structs import TopicPartition

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    deserialize_generated_event,
)
from synthetic_ops_generator.publishers.streaming import StreamingPublisher
from synthetic_ops_generator.replay.service import ReplayService
from synthetic_ops_generator.retention.sqlite import SQLiteEventStore
from synthetic_ops_generator.streaming.kafka import KafkaStreamTransport

TOPIC = "synthetic.operational.events"

BOOTSTRAP_SERVERS = os.getenv(
    "SYNTHETIC_OPS_KAFKA_BOOTSTRAP_SERVERS"
)


def make_event(
    *,
    event_id: str,
    sequence_number: int,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="replay.redpanda",
        event_time=datetime(
            2026,
            8,
            13,
            10,
            sequence_number,
            tzinfo=UTC,
        ),
        source_system="synthetic_replay",
        scenario_id="BANK-01",
        run_id="RUN9000001",
        chg_id="CHG9000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "message": f"replay-event-{sequence_number}",
        },
    )


@pytest.mark.asyncio
async def test_retained_run_replays_through_redpanda(
    tmp_path,
) -> None:
    if BOOTSTRAP_SERVERS is None:
        pytest.skip(
            "Redpanda integration environment is not configured."
        )

    database_path = tmp_path / "replay-events.db"

    first = make_event(
        event_id="EVT9000001",
        sequence_number=1,
    )

    second = make_event(
        event_id="EVT9000002",
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

    transport = KafkaStreamTransport(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        client_id="synthetic-ops-replay-producer",
    )

    publisher = StreamingPublisher(
        transport=transport,
        topic=TOPIC,
    )

    replay_service = ReplayService(
        store=replay_store,
        publisher=publisher,
    )

    consumer = AIOKafkaConsumer(
        bootstrap_servers=BOOTSTRAP_SERVERS,
        client_id="synthetic-ops-replay-consumer",
        enable_auto_commit=False,
    )

    await consumer.start()

    try:
        await consumer._client.force_metadata_update()
        await consumer.topics()

        partition_numbers = consumer.partitions_for_topic(
            TOPIC
        )

        if not partition_numbers:
            raise RuntimeError(
                f"No partitions found for topic {TOPIC}."
            )

        partitions = [
            TopicPartition(
                TOPIC,
                partition_number,
            )
            for partition_number in sorted(
                partition_numbers
            )
        ]

        consumer.assign(partitions)

        await consumer.seek_to_end(
            *partitions
        )

        await replay_store.start()
        await transport.start()

        try:
            replayed_count = (
                await replay_service.replay_run(
                    "RUN9000001"
                )
            )

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
            await replay_store.stop()

    finally:
        with suppress(asyncio.CancelledError):
            await consumer.stop()

    assert replayed_count == 2

    assert first_record.topic == TOPIC
    assert second_record.topic == TOPIC

    assert first_record.key == b"RUN9000001"
    assert second_record.key == b"RUN9000001"

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