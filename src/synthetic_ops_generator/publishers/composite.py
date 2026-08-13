from collections.abc import Sequence

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.base import EventPublisher


class CompositePublisher(EventPublisher):
    """
    Publishes each GeneratedEvent to multiple EventPublisher
    adapters in deterministic registration order.

    The CompositePublisher coordinates publication only.
    It does not modify, store, validate, or interpret events.
    """

    def __init__(
        self,
        publishers: Sequence[EventPublisher],
    ) -> None:
        if not publishers:
            raise ValueError(
                "CompositePublisher requires at least "
                "one publisher."
            )

        self._publishers = tuple(publishers)

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        for publisher in self._publishers:
            await publisher.publish(event)