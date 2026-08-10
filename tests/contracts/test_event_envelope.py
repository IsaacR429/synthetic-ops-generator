from datetime import UTC, datetime

from synthetic_ops_generator.events.envelope import GeneratedEvent


def test_valid_event_envelope() -> None:
    event = GeneratedEvent(
        event_id="EVT0000001",
        event_type="change.created",
        event_time=datetime.now(UTC),
        source_system="synthetic_itsm",
        scenario_id="BANK-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment="production",
        sequence_number=1,
        data={"risk": "medium"},
    )

    assert event.synthetic is True
    assert event.chg_id == "CHG0000001"