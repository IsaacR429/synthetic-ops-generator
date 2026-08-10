from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.scenarios.context import ScenarioContext


class SourceGenerator(ABC):
    """
    Contract implemented by every simulated enterprise source.
    """

    source_system: str

    @abstractmethod
    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        raise NotImplementedError