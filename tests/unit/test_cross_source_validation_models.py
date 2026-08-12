import pytest
from pydantic import ValidationError

from synthetic_ops_generator.validation.models import (
    CrossSourceValidationReport,
    ValidationFinding,
)


def test_validation_finding_accepts_valid_data() -> None:
    finding = ValidationFinding(
        requirement_id="REQ-COR-001",
        rule="change_correlation",
        message="CHG mismatch detected.",
        event_ids=[
            "EVT0000001",
            "EVT0000002",
        ],
    )

    assert finding.requirement_id == "REQ-COR-001"
    assert finding.rule == "change_correlation"

    assert finding.event_ids == [
        "EVT0000001",
        "EVT0000002",
    ]


def test_validation_finding_allows_no_event_ids() -> None:
    finding = ValidationFinding(
        requirement_id="REQ-COR-010",
        rule="chronology",
        message="Scenario chronology is invalid.",
    )

    assert finding.event_ids == []


def test_validation_finding_requires_requirement_id() -> None:
    with pytest.raises(ValidationError):
        ValidationFinding(
            requirement_id="",
            rule="change_correlation",
            message="CHG mismatch.",
        )


def test_validation_finding_requires_rule() -> None:
    with pytest.raises(ValidationError):
        ValidationFinding(
            requirement_id="REQ-COR-001",
            rule="",
            message="CHG mismatch.",
        )


def test_validation_finding_requires_message() -> None:
    with pytest.raises(ValidationError):
        ValidationFinding(
            requirement_id="REQ-COR-001",
            rule="change_correlation",
            message="",
        )


def test_empty_report_is_valid() -> None:
    report = CrossSourceValidationReport()

    assert report.is_valid is True
    assert report.findings == []


def test_report_with_finding_is_invalid() -> None:
    report = CrossSourceValidationReport(
        findings=[
            ValidationFinding(
                requirement_id="REQ-COR-001",
                rule="change_correlation",
                message="CHG mismatch.",
            )
        ]
    )

    assert report.is_valid is False


def test_report_can_add_finding() -> None:
    report = CrossSourceValidationReport()

    report.add_finding(
        requirement_id="REQ-COR-009",
        rule="evidence_reference",
        message=(
            "Evidence references unknown "
            "Event EVT9999999."
        ),
        event_ids=["EVT0000030"],
    )

    assert report.is_valid is False
    assert len(report.findings) == 1

    finding = report.findings[0]

    assert finding.requirement_id == "REQ-COR-009"
    assert finding.rule == "evidence_reference"
    assert finding.event_ids == ["EVT0000030"]


def test_report_accumulates_multiple_findings() -> None:
    report = CrossSourceValidationReport()

    report.add_finding(
        requirement_id="REQ-COR-001",
        rule="change_correlation",
        message="CHG mismatch.",
        event_ids=["EVT0000001"],
    )

    report.add_finding(
        requirement_id="REQ-COR-009",
        rule="evidence_reference",
        message="Evidence reference does not exist.",
        event_ids=["EVT0000030"],
    )

    assert report.is_valid is False
    assert len(report.findings) == 2

    assert [
        finding.requirement_id
        for finding in report.findings
    ] == [
        "REQ-COR-001",
        "REQ-COR-009",
    ]