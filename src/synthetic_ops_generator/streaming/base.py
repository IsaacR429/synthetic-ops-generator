from abc import ABC, abstractmethod


class StreamTransport(ABC):
    """
    Transport-neutral asynchronous stream delivery port.

    Concrete transports own their connection lifecycle.
    """

    @abstractmethod
    async def start(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send(
        self,
        *,
        topic: str,
        key: bytes,
        value: bytes,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def stop(self) -> None:
        raise NotImplementedError