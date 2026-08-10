from abc import ABC, abstractmethod

from synthetic_ops_generator.events.envelope import GeneratedEvent


class EventPublisher(ABC):

    @abstractmethod
    async def publish(self, event: GeneratedEvent) -> None:
        raise NotImplementedError