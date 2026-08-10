from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.validation.correlation import (
    CorrelationValidationError,
    validate_change_correlation,
)


def make_event(event_id: str, chg_id: str) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="test.event",
        event_time=datetime.now(UTC),
        source_system="test",
        scenario_id="BANK-01",
        run_id="RUN0000001",
        chg_id=chg_id,
        sequence_number=1,
    )


def test_valid_change_correlation() -> None:
    events = [
        make_event("EVT0000001", "CHG0000001"),
        make_event("EVT0000002", "CHG0000001"),
    ]

    validate_change_correlation(events, "CHG0000001")


def test_invalid_change_correlation() -> None:
    events = [
        make_event("EVT0000001", "CHG0000001"),
        make_event("EVT0000002", "CHG9999999"),
    ]

    with pytest.raises(CorrelationValidationError):
        validate_change_correlation(events, "CHG0000001")