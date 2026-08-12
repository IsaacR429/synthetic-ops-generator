from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.manual_validation import (
    ManualValidation,
    ManualValidationResult,
    ManualValidationStatus,
)


def requested_at() -> datetime:
    return datetime(
        2026,
        8,
        12,
        12,
        0,
        tzinfo=UTC,
    )


def completed_at() -> datetime:
    return datetime(
        2026,
        8,
        12,
        12,
        5,
        tzinfo=UTC,
    )


def build_completed_validation() -> ManualValidation:
    return ManualValidation(
        validation_id="VAL0000001",
        chg_id="CHG0000001",
        validation_type="business_validation",
        name="Business transaction validation",
        service="payment_service",
        component="payment_api",
        mandatory=True,
        status=ManualValidationStatus.COMPLETED,
        result=ManualValidationResult.PASSED,
        requested_at=requested_at(),
        completed_at=completed_at(),
        validated_by="operations_validator",
        evidence_reference="EVD0000001",
    )


def test_completed_manual_validation_accepts_valid_data() -> None:
    validation = build_completed_validation()

    assert validation.validation_id == "VAL0000001"
    assert validation.chg_id == "CHG0000001"
    assert validation.status == ManualValidationStatus.COMPLETED
    assert validation.result == ManualValidationResult.PASSED


def test_pending_validation_has_no_result() -> None:
    validation = ManualValidation(
        validation_id="VAL0000001",
        chg_id="CHG0000001",
        validation_type="business_validation",
        name="Business transaction validation",
        service="payment_service",
        mandatory=True,
        status=ManualValidationStatus.PENDING,
        requested_at=requested_at(),
    )

    assert validation.result is None
    assert validation.completed_at is None


def test_pending_validation_rejects_result() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot have a result",
    ):
        ManualValidation(
            validation_id="VAL0000001",
            chg_id="CHG0000001",
            validation_type="business_validation",
            name="Business transaction validation",
            service="payment_service",
            status=ManualValidationStatus.PENDING,
            result=ManualValidationResult.PASSED,
            requested_at=requested_at(),
        )


def test_completed_validation_requires_result() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a result",
    ):
        ManualValidation(
            validation_id="VAL0000001",
            chg_id="CHG0000001",
            validation_type="business_validation",
            name="Business transaction validation",
            service="payment_service",
            status=ManualValidationStatus.COMPLETED,
            requested_at=requested_at(),
            completed_at=completed_at(),
        )


def test_completed_validation_requires_completion_time() -> None:
    with pytest.raises(
        ValidationError,
        match="requires completed_at",
    ):
        ManualValidation(
            validation_id="VAL0000001",
            chg_id="CHG0000001",
            validation_type="business_validation",
            name="Business transaction validation",
            service="payment_service",
            status=ManualValidationStatus.COMPLETED,
            result=ManualValidationResult.PASSED,
            requested_at=requested_at(),
        )


def test_completion_cannot_precede_request() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot precede requested_at",
    ):
        ManualValidation(
            validation_id="VAL0000001",
            chg_id="CHG0000001",
            validation_type="business_validation",
            name="Business transaction validation",
            service="payment_service",
            status=ManualValidationStatus.COMPLETED,
            result=ManualValidationResult.PASSED,
            requested_at=completed_at(),
            completed_at=requested_at(),
        )


def test_waived_validation_requires_reason() -> None:
    with pytest.raises(
        ValidationError,
        match="requires a waiver reason",
    ):
        ManualValidation(
            validation_id="VAL0000001",
            chg_id="CHG0000001",
            validation_type="business_validation",
            name="Business transaction validation",
            service="payment_service",
            status=ManualValidationStatus.COMPLETED,
            result=ManualValidationResult.WAIVED,
            requested_at=requested_at(),
            completed_at=completed_at(),
        )


def test_waived_validation_accepts_reason() -> None:
    validation = ManualValidation(
        validation_id="VAL0000001",
        chg_id="CHG0000001",
        validation_type="business_validation",
        name="Business transaction validation",
        service="payment_service",
        status=ManualValidationStatus.COMPLETED,
        result=ManualValidationResult.WAIVED,
        requested_at=requested_at(),
        completed_at=completed_at(),
        waiver_reason="Approved temporary exception.",
    )

    assert validation.result == ManualValidationResult.WAIVED
    assert (
        validation.waiver_reason
        == "Approved temporary exception."
    )


def test_manual_validation_supports_evidence_reference() -> None:
    validation = build_completed_validation()

    assert validation.evidence_reference == "EVD0000001"


def test_manual_validation_rejects_naive_timestamp() -> None:
    naive_time = requested_at().replace(
        tzinfo=None
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        ManualValidation(
            validation_id="VAL0000001",
            chg_id="CHG0000001",
            validation_type="business_validation",
            name="Business transaction validation",
            service="payment_service",
            status=ManualValidationStatus.PENDING,
            requested_at=naive_time,
        )