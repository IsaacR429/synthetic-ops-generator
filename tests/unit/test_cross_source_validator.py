from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)

BASE_TIME = datetime(
    2026,
    8,
    13,
    10,
    0,
    tzinfo=UTC,
)


def build_context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_event(
    *,
    sequence_number: int,
    event_id: str | None = None,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=(
            event_id
            or f"EVT{sequence_number:07d}"
        ),
        event_type="test.event",
        event_time=(
            BASE_TIME
            + timedelta(
                seconds=sequence_number * 5
            )
        ),
        source_system="synthetic_test",
        scenario_id="TEST-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component=None,
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
    )


def build_valid_events() -> list[GeneratedEvent]:
    return [
        build_event(sequence_number=1),
        build_event(sequence_number=2),
        build_event(sequence_number=3),
    ]


def finding_rules(
    report,
) -> set[str]:
    return {
        finding.rule
        for finding in report.findings
    }


def test_valid_correlated_run_passes() -> None:
    report = CrossSourceValidator().validate(
        events=build_valid_events(),
        context=build_context(),
    )

    assert report.is_valid is True
    assert report.findings == []


def test_duplicate_event_id_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "event_id": events[0].event_id,
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert report.is_valid is False
    assert "unique_event_id" in finding_rules(
        report
    )


def test_duplicate_sequence_number_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "sequence_number": 1,
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "unique_sequence_number" in finding_rules(
        report
    )


def test_scenario_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "scenario_id": "OTHER-01",
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "scenario_correlation" in finding_rules(
        report
    )


def test_run_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "run_id": "RUN9999999",
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "run_correlation" in finding_rules(
        report
    )


def test_change_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "chg_id": "CHG9999999",
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "change_correlation" in finding_rules(
        report
    )


def test_missing_optional_change_id_is_allowed() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "chg_id": None,
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "change_correlation" not in finding_rules(
        report
    )


def test_business_stream_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "business_stream": "lending",
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert (
        "business_stream_correlation"
        in finding_rules(report)
    )


def test_service_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "service": "other_service",
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "service_correlation" in finding_rules(
        report
    )


def test_sequence_order_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[0] = events[0].model_copy(
        update={
            "sequence_number": 2,
        }
    )

    events[1] = events[1].model_copy(
        update={
            "sequence_number": 1,
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "sequence_chronology" in finding_rules(
        report
    )


def test_timestamp_order_mismatch_is_reported() -> None:
    events = build_valid_events()

    events[1] = events[1].model_copy(
        update={
            "event_time": (
                events[0].event_time
                - timedelta(seconds=1)
            ),
        }
    )

    report = CrossSourceValidator().validate(
        events=events,
        context=build_context(),
    )

    assert "timestamp_chronology" in finding_rules(
        report
    )