from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import (
    Criticality,
    Environment,
    Industry,
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


def build_enterprise() -> Enterprise:
    return Enterprise(
        enterprise_id="bank_alpha",
        name="Bank Alpha",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(
                stream_id="payments",
                name="Payments",
            ),
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="Payments Team",
                criticality=Criticality.CRITICAL,
            ),
        ],
        components=[
            Component(
                component_id="payment_api",
                name="Payment API",
                component_type="api",
                service_id="payment_service",
                environment=Environment.PRODUCTION,
            ),
        ],
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
    component: str | None = None,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=f"EVT{sequence_number:07d}",
        event_type="test.event",
        event_time=(
            BASE_TIME
            + timedelta(seconds=sequence_number * 5)
        ),
        source_system="synthetic_test",
        scenario_id="TEST-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component=component,
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
    )


def validate(
    events: list[GeneratedEvent],
):
    return CrossSourceValidator().validate(
        events=events,
        context=build_context(),
        enterprise=build_enterprise(),
    )


def test_valid_enterprise_references_pass() -> None:
    report = validate([
        build_event(
            sequence_number=1,
            component="payment_api",
        )
    ])

    assert report.is_valid is True


def test_unknown_business_stream_is_reported() -> None:
    event = build_event(sequence_number=1).model_copy(
        update={"business_stream": "unknown_stream"}
    )

    report = validate([event])

    assert any(
        finding.rule == "business_stream_reference"
        for finding in report.findings
    )


def test_unknown_service_is_reported() -> None:
    event = build_event(sequence_number=1).model_copy(
        update={"service": "unknown_service"}
    )

    report = validate([event])

    assert any(
        finding.rule == "service_reference"
        for finding in report.findings
    )


def test_service_business_stream_mismatch_is_reported() -> None:
    event = build_event(sequence_number=1).model_copy(
        update={"business_stream": "unknown_stream"}
    )

    enterprise = build_enterprise()

    enterprise.business_streams.append(
        BusinessStream(
            stream_id="unknown_stream",
            name="Other Stream",
        )
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
    )

    assert any(
        finding.rule
        == "service_business_stream_relationship"
        for finding in report.findings
    )


def test_unknown_component_is_reported() -> None:
    event = build_event(
        sequence_number=1,
        component="unknown_component",
    )

    report = validate([event])

    assert any(
        finding.rule == "component_reference"
        for finding in report.findings
    )


def test_component_service_mismatch_is_reported() -> None:
    enterprise = build_enterprise()

    enterprise.components[0] = (
        enterprise.components[0].model_copy(
            update={"service_id": "other_service"}
        )
    )

    event = build_event(
        sequence_number=1,
        component="payment_api",
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
    )

    assert any(
        finding.rule
        == "component_service_relationship"
        for finding in report.findings
    )


def test_component_environment_mismatch_is_reported() -> None:
    event = build_event(
        sequence_number=1,
        component="payment_api",
    ).model_copy(
        update={"environment": Environment.TEST}
    )

    report = validate([event])

    assert any(
        finding.rule
        == "component_environment_relationship"
        for finding in report.findings
    )


def test_valid_evidence_reference_passes() -> None:
    source_event = build_event(sequence_number=1)

    evidence_event = build_event(
        sequence_number=2
    ).model_copy(
        update={
            "event_type": "evidence.captured",
            "data": {
                "evidence": {
                    "source_event_ids": [
                        source_event.event_id,
                    ],
                    "source_record_ids": [],
                }
            },
        }
    )

    report = validate([
        source_event,
        evidence_event,
    ])

    assert report.is_valid is True


def test_missing_evidence_event_reference_is_reported() -> None:
    evidence_event = build_event(
        sequence_number=2
    ).model_copy(
        update={
            "event_type": "evidence.captured",
            "data": {
                "evidence": {
                    "source_event_ids": [
                        "EVT9999999",
                    ],
                    "source_record_ids": [],
                }
            },
        }
    )

    report = validate([evidence_event])

    assert any(
        finding.rule == "evidence_event_reference"
        for finding in report.findings
    )


def test_future_evidence_reference_is_reported() -> None:
    evidence_event = build_event(
        sequence_number=1
    ).model_copy(
        update={
            "event_type": "evidence.captured",
            "data": {
                "evidence": {
                    "source_event_ids": [
                        "EVT0000002",
                    ],
                    "source_record_ids": [],
                }
            },
        }
    )

    future_event = build_event(sequence_number=2)

    report = validate([
        evidence_event,
        future_event,
    ])

    assert any(
        finding.rule
        == "evidence_reference_chronology"
        for finding in report.findings
    )
