from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.base import EventPublisher


class InMemoryPublisher(EventPublisher):

    def __init__(self) -> None:
        self.events: list[GeneratedEvent] = []

    async def publish(self, event: GeneratedEvent) -> None:
        self.events.append(event)

    def clear(self) -> None:
        self.events.clear()