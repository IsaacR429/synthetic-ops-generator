from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.retention.base import EventStore


class RetentionPublisher(EventPublisher):
    """
    Persists canonical GeneratedEvents through an EventStore.

    The publisher does not implement storage mechanics or replay.
    """

    def __init__(
        self,
        *,
        store: EventStore,
    ) -> None:
        self._store = store

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        await self._store.append(event)
