import pytest

from synthetic_ops_generator.streaming.kafka import (
    KafkaStreamTransport,
)


def test_kafka_transport_rejects_empty_bootstrap_servers() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "KafkaStreamTransport requires "
            "bootstrap servers"
        ),
    ):
        KafkaStreamTransport(
            bootstrap_servers="   "
        )


def test_kafka_transport_rejects_empty_client_id() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "KafkaStreamTransport requires "
            "a client ID"
        ),
    ):
        KafkaStreamTransport(
            bootstrap_servers="localhost:19092",
            client_id="   ",
        )


@pytest.mark.asyncio
async def test_kafka_transport_requires_start_before_send() -> None:
    transport = KafkaStreamTransport(
        bootstrap_servers="localhost:19092"
    )

    with pytest.raises(
        RuntimeError,
        match="KafkaStreamTransport is not started",
    ):
        await transport.send(
            topic="synthetic.operational.events",
            key=b"RUN0000001",
            value=b"test",
        )


@pytest.mark.asyncio
async def test_kafka_transport_stop_before_start_is_safe() -> None:
    transport = KafkaStreamTransport(
        bootstrap_servers="localhost:19092"
    )

    await transport.stop()