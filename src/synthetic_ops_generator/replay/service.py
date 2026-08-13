from synthetic_ops_generator.publishers.base import EventPublisher
from synthetic_ops_generator.retention.base import EventStore


class ReplayService:
    """
    Replays retained canonical events through an EventPublisher.

    Replay preserves the stored event contract and publication order.
    It does not regenerate, modify, or reinterpret events.
    """

    def __init__(
        self,
        *,
        store: EventStore,
        publisher: EventPublisher,
    ) -> None:
        self._store = store
        self._publisher = publisher

    async def replay_run(
        self,
        run_id: str,
    ) -> int:
        if not run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        events = await self._store.get_run_events(
            run_id
        )

        for event in events:
            await self._publisher.publish(event)

        return len(events)