from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.evidence import Evidence


def captured_at() -> datetime:
    return datetime(
        2026,
        8,
        13,
        10,
        0,
        tzinfo=UTC,
    )


def build_evidence() -> Evidence:
    return Evidence(
        evidence_id="EVD0000001",
        chg_id="CHG0000001",
        evidence_type="deployment_result",
        title="Successful deployment result",
        service="payment_service",
        component="payment_api",
        captured_at=captured_at(),
        source_event_ids=["EVT0000014"],
        source_record_ids=["DEP0000001"],
    )


def test_evidence_accepts_valid_data() -> None:
    evidence = build_evidence()

    assert evidence.evidence_id == "EVD0000001"
    assert evidence.chg_id == "CHG0000001"
    assert evidence.evidence_type == "deployment_result"


def test_evidence_supports_event_references() -> None:
    evidence = build_evidence()

    assert evidence.source_event_ids == [
        "EVT0000014"
    ]


def test_evidence_supports_record_references() -> None:
    evidence = build_evidence()

    assert evidence.source_record_ids == [
        "DEP0000001"
    ]


def test_evidence_can_reference_only_events() -> None:
    evidence = Evidence(
        evidence_id="EVD0000001",
        chg_id="CHG0000001",
        evidence_type="post_change_observation",
        title="Post-change observation",
        service="payment_service",
        captured_at=captured_at(),
        source_event_ids=[
            "EVT0000021",
            "EVT0000022",
            "EVT0000023",
        ],
    )

    assert evidence.source_record_ids == []


def test_evidence_can_reference_only_records() -> None:
    evidence = Evidence(
        evidence_id="EVD0000001",
        chg_id="CHG0000001",
        evidence_type="change_approval",
        title="Approved Change",
        service="payment_service",
        captured_at=captured_at(),
        source_record_ids=[
            "CHG0000001",
            "APR0000001",
        ],
    )

    assert evidence.source_event_ids == []


def test_evidence_requires_source_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="must reference at least one",
    ):
        Evidence(
            evidence_id="EVD0000001",
            chg_id="CHG0000001",
            evidence_type="deployment_result",
            title="Successful deployment result",
            service="payment_service",
            captured_at=captured_at(),
        )


def test_evidence_rejects_empty_reference() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot be empty",
    ):
        Evidence(
            evidence_id="EVD0000001",
            chg_id="CHG0000001",
            evidence_type="deployment_result",
            title="Successful deployment result",
            service="payment_service",
            captured_at=captured_at(),
            source_event_ids=[""],
        )


def test_evidence_rejects_duplicate_event_references() -> None:
    with pytest.raises(
        ValidationError,
        match="source_event_ids.*duplicates",
    ):
        Evidence(
            evidence_id="EVD0000001",
            chg_id="CHG0000001",
            evidence_type="deployment_result",
            title="Successful deployment result",
            service="payment_service",
            captured_at=captured_at(),
            source_event_ids=[
                "EVT0000014",
                "EVT0000014",
            ],
        )


def test_evidence_rejects_duplicate_record_references() -> None:
    with pytest.raises(
        ValidationError,
        match="source_record_ids.*duplicates",
    ):
        Evidence(
            evidence_id="EVD0000001",
            chg_id="CHG0000001",
            evidence_type="deployment_result",
            title="Successful deployment result",
            service="payment_service",
            captured_at=captured_at(),
            source_record_ids=[
                "DEP0000001",
                "DEP0000001",
            ],
        )


def test_evidence_rejects_naive_timestamp() -> None:
    naive_time = captured_at().replace(
        tzinfo=None
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        Evidence(
            evidence_id="EVD0000001",
            chg_id="CHG0000001",
            evidence_type="deployment_result",
            title="Successful deployment result",
            service="payment_service",
            captured_at=naive_time,
            source_record_ids=["DEP0000001"],
        )


def test_evidence_supports_service_level_scope() -> None:
    evidence = Evidence(
        evidence_id="EVD0000001",
        chg_id="CHG0000001",
        evidence_type="pre_change_baseline",
        title="Pre-change operational baseline",
        service="payment_service",
        component=None,
        captured_at=captured_at(),
        source_event_ids=[
            "EVT0000003",
            "EVT0000004",
            "EVT0000005",
        ],
    )

    assert evidence.component is None


def test_evidence_supports_structured_attributes() -> None:
    evidence = Evidence(
        evidence_id="EVD0000001",
        chg_id="CHG0000001",
        evidence_type="application_validation",
        title="Application validation results",
        service="payment_service",
        captured_at=captured_at(),
        source_event_ids=[
            "EVT0000016",
            "EVT0000018",
            "EVT0000020",
        ],
        attributes={
            "validation_type": "automated",
            "mandatory": True,
        },
    )

    assert (
        evidence.attributes["validation_type"]
        == "automated"
    )
    assert evidence.attributes["mandatory"] is True