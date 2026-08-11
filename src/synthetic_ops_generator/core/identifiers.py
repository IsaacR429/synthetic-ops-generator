from collections import defaultdict
from threading import Lock


class IdFactory:
    """
    Central authority for generator identifiers.

    Individual generators must not create their own IDs.
    """

    def __init__(self) -> None:
        self._counters: dict[str, int] = defaultdict(int)
        self._lock = Lock()

    def next(self, prefix: str, width: int = 7) -> str:
        with self._lock:
            self._counters[prefix] += 1
            value = self._counters[prefix]

        return f"{prefix}{value:0{width}d}"

    def change_id(self) -> str:
        return self.next("CHG")

    def run_id(self) -> str:
        return self.next("RUN")

    def event_id(self) -> str:
        return self.next("EVT")

    def deployment_id(self) -> str:
        return self.next("DEP")

    def approval_id(self) -> str:
        return self.next("APR")

    def test_id(self) -> str:
        return self.next("TST")

    def incident_id(self) -> str:
        return self.next("INC")

    def evidence_id(self) -> str:
        return self.next("EVD")

    def validation_id(self) -> str:
        return self.next("VAL")