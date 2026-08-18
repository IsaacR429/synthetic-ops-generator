from dataclasses import dataclass

from synthetic_ops_generator.domain.enums import SourceDomain


@dataclass(frozen=True)
class EventQuery:
    """
    Run-scoped filters for retained canonical events.

    None means that the corresponding projection field
    is not used as a filter.
    """

    run_id: str

    source_domain: SourceDomain | None = None
    source_system: str | None = None
    event_type: str | None = None
    service: str | None = None
    component: str | None = None
