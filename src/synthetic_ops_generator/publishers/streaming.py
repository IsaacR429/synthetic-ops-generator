from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    serialize_generated_event,
)
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.streaming.base import StreamTransport


class StreamingPublisher(EventPublisher):
    """
    Publishes canonical GeneratedEvents through a StreamTransport.

    Events are serialized using the canonical event serializer.
    Run ID is used as the stream key to support per-Run ordering
    in partitioned streaming systems.
    """

    def __init__(
        self,
        *,
        transport: StreamTransport,
        topic: str,
    ) -> None:
        normalized_topic = topic.strip()

        if not normalized_topic:
            raise ValueError(
                "StreamingPublisher requires a topic."
            )

        self._transport = transport
        self._topic = normalized_topic

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        await self._transport.send(
            topic=self._topic,
            key=event.run_id.encode("utf-8"),
            value=serialize_generated_event(event),
        )
