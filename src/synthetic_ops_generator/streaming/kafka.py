from aiokafka import AIOKafkaProducer

from synthetic_ops_generator.streaming.base import StreamTransport


class KafkaStreamTransport(StreamTransport):
    """
    Kafka-protocol StreamTransport backed by AIOKafkaProducer.

    The transport owns producer connection lifecycle only.
    Event serialization, topic selection, and stream keys remain
    responsibilities of StreamingPublisher.
    """

    def __init__(
        self,
        *,
        bootstrap_servers: str,
        client_id: str = "synthetic-ops-generator",
    ) -> None:
        normalized_servers = bootstrap_servers.strip()
        normalized_client_id = client_id.strip()

        if not normalized_servers:
            raise ValueError(
                "KafkaStreamTransport requires "
                "bootstrap servers."
            )

        if not normalized_client_id:
            raise ValueError(
                "KafkaStreamTransport requires "
                "a client ID."
            )

        self._bootstrap_servers = normalized_servers
        self._client_id = normalized_client_id
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        if self._producer is not None:
            return

        producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
        )

        await producer.start()

        self._producer = producer

    async def send(
        self,
        *,
        topic: str,
        key: bytes,
        value: bytes,
    ) -> None:
        if self._producer is None:
            raise RuntimeError(
                "KafkaStreamTransport is not started."
            )

        await self._producer.send_and_wait(
            topic,
            value=value,
            key=key,
        )

    async def stop(self) -> None:
        if self._producer is None:
            return

        producer = self._producer

        await producer.stop()

        self._producer = None