from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.governance.exceptions import (
    PolicyException,
    PolicyExceptionScope,
    PolicyExceptionStatus,
    PolicyExceptionType,
)


def _dt(
    day: int,
    hour: int = 12,
) -> datetime:
    return datetime(
        2026,
        6,
        day,
        hour,
        tzinfo=timezone.utc,
    )


def _requested_control_waiver() -> PolicyException:
    return PolicyException(
        exception_id="EXC-CHANGE-001",
        exception_type=PolicyExceptionType.WAIVER,
        status=PolicyExceptionStatus.REQUESTED,
        policy_id="POL-CHANGE-0042",
        control_id="CTRL-POST-CHANGE-VALIDATION",
        scope=PolicyExceptionScope.CONTROL,
        reason=(
            "Emergency production recovery requires "
            "temporary deviation from normal validation."
        ),
        requested_by="incident-commander@example.test",
        requested_on=_dt(10),
        source_reference="CHG-2026-001",
    )


def _approved_control_waiver() -> PolicyException:
    return PolicyException(
        exception_id="EXC-CHANGE-001",
        exception_type=PolicyExceptionType.WAIVER,
        status=PolicyExceptionStatus.APPROVED,
        policy_id="POL-CHANGE-0042",
        control_id="CTRL-POST-CHANGE-VALIDATION",
        scope=PolicyExceptionScope.CONTROL,
        reason=(
            "Emergency production recovery requires "
            "temporary deviation from normal validation."
        ),
        requested_by="incident-commander@example.test",
        requested_on=_dt(10),
        decided_by="change-authority@example.test",
        decided_on=_dt(10, 13),
        decision_reference="CAB-DECISION-2026-441",
        valid_from=_dt(10, 13),
        valid_to=_dt(11, 1),
        source_reference="CHG-2026-001",
    )


def test_requested_control_waiver_is_valid() -> None:
    waiver = _requested_control_waiver()

    assert waiver.status == PolicyExceptionStatus.REQUESTED
    assert waiver.scope == PolicyExceptionScope.CONTROL
    assert waiver.requirement_ids == ()


def test_requirement_scoped_waiver_requires_requirement_ids() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REQ-001",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REQUESTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.REQUIREMENT,
            requirement_ids=(),
            reason="Temporary requirement-specific deviation.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
        )


def test_requirement_scoped_waiver_preserves_requirement_order() -> None:
    waiver = PolicyException(
        exception_id="EXC-REQ-001",
        exception_type=PolicyExceptionType.WAIVER,
        status=PolicyExceptionStatus.REQUESTED,
        policy_id="POL-CHANGE-0042",
        control_id="CTRL-POST-CHANGE-VALIDATION",
        scope=PolicyExceptionScope.REQUIREMENT,
        requirement_ids=(
            "REQ-SMOKE-001",
            "REQ-TRANSACTION-001",
        ),
        reason="Temporary requirement-specific deviation.",
        requested_by="operator@example.test",
        requested_on=_dt(10),
    )

    assert waiver.requirement_ids == (
        "REQ-SMOKE-001",
        "REQ-TRANSACTION-001",
    )


def test_requirement_scope_rejects_duplicate_requirement_ids() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REQ-DUPLICATE",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REQUESTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.REQUIREMENT,
            requirement_ids=(
                "REQ-SMOKE-001",
                "REQ-SMOKE-001",
            ),
            reason="Invalid duplicate requirement scope.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
        )


def test_control_scope_rejects_requirement_ids() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-CONTROL-BAD",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REQUESTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            requirement_ids=(
                "REQ-SMOKE-001",
            ),
            reason="Invalid mixed scope.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
        )


def test_requested_waiver_rejects_decision_metadata() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REQUESTED-BAD",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REQUESTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Requested but not yet decided.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
            decision_reference="DECISION-001",
        )


def test_requested_waiver_rejects_effective_validity() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REQUESTED-VALIDITY",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REQUESTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Requested waiver cannot already be effective.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            valid_from=_dt(10, 13),
            valid_to=_dt(11, 1),
        )


def test_approved_waiver_requires_decision_metadata() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-APPROVED-NO-DECISION",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.APPROVED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Invalid approved waiver.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            valid_from=_dt(10, 13),
            valid_to=_dt(11, 1),
        )


def test_approved_waiver_requires_finite_validity() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-APPROVED-NO-EXPIRY",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.APPROVED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Perpetual waiver must not be implicit.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
            decision_reference="DECISION-001",
            valid_from=_dt(10, 13),
            valid_to=None,
        )


def test_approved_waiver_rejects_invalid_validity_order() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-APPROVED-BAD-WINDOW",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.APPROVED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Invalid waiver window.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
            decision_reference="DECISION-001",
            valid_from=_dt(11, 1),
            valid_to=_dt(10, 13),
        )


def test_approved_waiver_is_valid_with_finite_window() -> None:
    waiver = _approved_control_waiver()

    assert waiver.status == PolicyExceptionStatus.APPROVED
    assert waiver.valid_from == _dt(10, 13)
    assert waiver.valid_to == _dt(11, 1)


def test_rejected_waiver_requires_decision_metadata() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REJECTED-BAD",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REJECTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Rejected request.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
        )


def test_rejected_waiver_cannot_have_validity_window() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REJECTED-WINDOW",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REJECTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Rejected request.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
            decision_reference="DECISION-REJECT-001",
            valid_from=_dt(10, 13),
            valid_to=_dt(11, 1),
        )


def test_revoked_waiver_requires_revocation_metadata() -> None:
    approved = _approved_control_waiver()

    with pytest.raises(ValidationError):
        PolicyException(
            **{
                **approved.model_dump(),
                "status": PolicyExceptionStatus.REVOKED,
            }
        )


def test_revoked_waiver_is_valid_with_complete_history() -> None:
    waiver = PolicyException(
        **{
            **_approved_control_waiver().model_dump(),
            "status": PolicyExceptionStatus.REVOKED,
            "revoked_by": "change-authority@example.test",
            "revoked_on": _dt(10, 18),
            "revocation_reason": (
                "Normal validation capability restored."
            ),
        }
    )

    assert waiver.status == PolicyExceptionStatus.REVOKED
    assert waiver.revoked_on == _dt(10, 18)


def test_revocation_cannot_precede_approval_decision() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            **{
                **_approved_control_waiver().model_dump(),
                "status": PolicyExceptionStatus.REVOKED,
                "revoked_by": "change-authority@example.test",
                "revoked_on": _dt(10, 12),
                "revocation_reason": "Invalid chronology.",
            }
        )


def test_requested_on_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-NAIVE",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REQUESTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Invalid timestamp.",
            requested_by="operator@example.test",
            requested_on=datetime(2026, 6, 10, 12),
        )


def test_decision_cannot_precede_request() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-BAD-DECISION-TIME",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.APPROVED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Invalid chronology.",
            requested_by="operator@example.test",
            requested_on=_dt(10, 14),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
            decision_reference="DECISION-001",
            valid_from=_dt(10, 13),
            valid_to=_dt(11, 1),
        )


def test_policy_exception_is_frozen() -> None:
    waiver = _requested_control_waiver()

    with pytest.raises(Exception):
        waiver.status = PolicyExceptionStatus.APPROVED


def test_policy_exception_does_not_model_enforcement() -> None:
    fields = PolicyException.model_fields

    assert "blocking" not in fields
    assert "compliance" not in fields
    assert "action" not in fields
    assert "outcome" not in fields
    assert "requirement_assessments" not in fields

def test_approved_validity_cannot_start_before_decision() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-RETROACTIVE",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.APPROVED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Invalid retroactive activation.",
            requested_by="operator@example.test",
            requested_on=_dt(10, 10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 14),
            decision_reference="DECISION-RETROACTIVE",
            valid_from=_dt(10, 13),
            valid_to=_dt(11, 1),
        )


def test_approved_validity_may_start_at_decision() -> None:
    waiver = PolicyException(
        exception_id="EXC-IMMEDIATE",
        exception_type=PolicyExceptionType.WAIVER,
        status=PolicyExceptionStatus.APPROVED,
        policy_id="POL-CHANGE-0042",
        control_id="CTRL-POST-CHANGE-VALIDATION",
        scope=PolicyExceptionScope.CONTROL,
        reason="Waiver becomes effective upon approval.",
        requested_by="operator@example.test",
        requested_on=_dt(10, 10),
        decided_by="approver@example.test",
        decided_on=_dt(10, 14),
        decision_reference="DECISION-IMMEDIATE",
        valid_from=_dt(10, 14),
        valid_to=_dt(11, 1),
    )

    assert waiver.valid_from == waiver.decided_on


def test_rejected_waiver_rejects_partial_decision_metadata() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-REJECTED-PARTIAL",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.REJECTED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Incomplete rejection authority.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
        )


def test_approved_validity_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError):
        PolicyException(
            exception_id="EXC-NAIVE-VALIDITY",
            exception_type=PolicyExceptionType.WAIVER,
            status=PolicyExceptionStatus.APPROVED,
            policy_id="POL-CHANGE-0042",
            control_id="CTRL-POST-CHANGE-VALIDATION",
            scope=PolicyExceptionScope.CONTROL,
            reason="Invalid naive validity timestamp.",
            requested_by="operator@example.test",
            requested_on=_dt(10),
            decided_by="approver@example.test",
            decided_on=_dt(10, 13),
            decision_reference="DECISION-NAIVE",
            valid_from=datetime(
                2026,
                6,
                10,
                13,
            ),
            valid_to=_dt(11, 1),
        )


def test_exception_record_does_not_embed_resolution_state() -> None:
    fields = PolicyException.model_fields

    assert "activation_status" not in fields
    assert "active_requirement_ids" not in fields
    assert "applicability_status" not in fields
    assert "effective_exception" not in fields
