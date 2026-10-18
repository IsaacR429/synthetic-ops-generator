from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from synthetic_ops_generator.checks.requirements import (
    CheckRequirement,
    RequirementObligation,
)
from synthetic_ops_generator.governance.activation import (
    ControlActivationResult,
    ControlActivationStatus,
)
from synthetic_ops_generator.governance.applicability import (
    ControlApplicabilityStatus,
)
from synthetic_ops_generator.governance.exception_resolution import (
    PolicyExceptionResolutionStatus,
    resolve_policy_exception,
)
from synthetic_ops_generator.governance.exceptions import (
    PolicyException,
    PolicyExceptionScope,
    PolicyExceptionStatus,
    PolicyExceptionType,
)
from synthetic_ops_generator.governance.models import (
    GovernanceAuthority,
    GovernanceAuthorityType,
    PolicyApplicability,
    PolicyCatalogue,
    PolicyControl,
    PolicyDocument,
)


POLICY_ID = "POL-CHANGE-0042"
OTHER_POLICY_ID = "POL-CHANGE-OTHER"

CONTROL_ID = "CTRL-POST-CHANGE-VALIDATION"

REQ_SMOKE = "REQ-SMOKE-001"
REQ_TRANSACTION = "REQ-TRANSACTION-001"


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


def _requirement(
    requirement_id: str,
) -> CheckRequirement:
    return CheckRequirement(
        requirement_id=requirement_id,
        check_definition_id=(
            "application.post_deployment_smoke"
        ),
        obligation=RequirementObligation.REQUIRED,
        rationale="Enterprise validation requirement.",
    )


def _catalogue() -> PolicyCatalogue:
    authority = GovernanceAuthority(
        authority_id="AUTH-CHANGE-MGMT",
        authority_type=(
            GovernanceAuthorityType.ENTERPRISE_STANDARD
        ),
        name="Enterprise Change Management",
    )

    policy = PolicyDocument(
        policy_id=POLICY_ID,
        title="Enterprise Change Management Standard",
        version="4.2",
        owner="Enterprise Change Management",
        authority_id=authority.authority_id,
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
    )

    other_policy = PolicyDocument(
        policy_id=OTHER_POLICY_ID,
        title="Other Enterprise Standard",
        version="1.0",
        owner="Enterprise Governance",
        authority_id=authority.authority_id,
        effective_from=date(2026, 1, 1),
        effective_to=None,
    )

    control = PolicyControl(
        control_id=CONTROL_ID,
        policy_id=POLICY_ID,
        control_reference="4.2.3",
        title="Production post-change validation",
        objective=(
            "Require appropriate post-change validation."
        ),
        applicability=PolicyApplicability(),
        requirement_ids=(
            REQ_SMOKE,
            REQ_TRANSACTION,
        ),
    )

    return PolicyCatalogue(
        authorities={
            authority.authority_id: authority,
        },
        policies={
            policy.policy_id: policy,
            other_policy.policy_id: other_policy,
        },
        controls={
            control.control_id: control,
        },
        requirements={
            REQ_SMOKE: _requirement(REQ_SMOKE),
            REQ_TRANSACTION: _requirement(
                REQ_TRANSACTION
            ),
        },
    )


def _activation(
    *,
    status: ControlActivationStatus = (
        ControlActivationStatus.ACTIVE
    ),
    policy_id: str = POLICY_ID,
    control_id: str = CONTROL_ID,
    evaluated_on: date = date(2026, 6, 10),
) -> ControlActivationResult:
    active_requirement_ids = (
        (
            REQ_SMOKE,
            REQ_TRANSACTION,
        )
        if status == ControlActivationStatus.ACTIVE
        else ()
    )

    return ControlActivationResult(
        policy_id=policy_id,
        control_id=control_id,
        evaluated_on=evaluated_on,
        applicability_status=(
            ControlApplicabilityStatus.APPLICABLE
        ),
        status=status,
        active_requirement_ids=(
            active_requirement_ids
        ),
    )


def _approved_control_waiver() -> PolicyException:
    return PolicyException(
        exception_id="EXC-CONTROL-001",
        exception_type=PolicyExceptionType.WAIVER,
        status=PolicyExceptionStatus.APPROVED,
        policy_id=POLICY_ID,
        control_id=CONTROL_ID,
        scope=PolicyExceptionScope.CONTROL,
        reason="Temporary approved operational deviation.",
        requested_by="operator@example.test",
        requested_on=_dt(9, 10),
        decided_by="approver@example.test",
        decided_on=_dt(9, 11),
        decision_reference="CAB-2026-441",
        valid_from=_dt(10, 9),
        valid_to=_dt(11, 1),
    )


def _approved_requirement_waiver() -> PolicyException:
    return PolicyException(
        exception_id="EXC-REQ-001",
        exception_type=PolicyExceptionType.WAIVER,
        status=PolicyExceptionStatus.APPROVED,
        policy_id=POLICY_ID,
        control_id=CONTROL_ID,
        scope=PolicyExceptionScope.REQUIREMENT,
        requirement_ids=(
            REQ_TRANSACTION,
        ),
        reason="Temporary requirement-specific deviation.",
        requested_by="operator@example.test",
        requested_on=_dt(9, 10),
        decided_by="approver@example.test",
        decided_on=_dt(9, 11),
        decision_reference="CAB-2026-442",
        valid_from=_dt(10, 9),
        valid_to=_dt(11, 1),
    )


def test_control_scoped_approved_waiver_is_effective() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(10, 12),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EFFECTIVE
    )

    assert result.effective_requirement_ids == (
        REQ_SMOKE,
        REQ_TRANSACTION,
    )


def test_requirement_scoped_waiver_exposes_only_targeted_requirements() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=_approved_requirement_waiver(),
        evaluated_at=_dt(10, 12),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EFFECTIVE
    )

    assert result.effective_requirement_ids == (
        REQ_TRANSACTION,
    )


@pytest.mark.parametrize(
    "lifecycle_status",
    [
        PolicyExceptionStatus.REQUESTED,
        PolicyExceptionStatus.REJECTED,
    ],
)
def test_unapproved_exception_is_not_approved(
    lifecycle_status: PolicyExceptionStatus,
) -> None:
    if lifecycle_status == PolicyExceptionStatus.REQUESTED:
        exception = PolicyException(
            exception_id="EXC-UNAPPROVED",
            exception_type=PolicyExceptionType.WAIVER,
            status=lifecycle_status,
            policy_id=POLICY_ID,
            control_id=CONTROL_ID,
            scope=PolicyExceptionScope.CONTROL,
            reason="Pending waiver request.",
            requested_by="operator@example.test",
            requested_on=_dt(9, 10),
        )
    else:
        exception = PolicyException(
            exception_id="EXC-UNAPPROVED",
            exception_type=PolicyExceptionType.WAIVER,
            status=lifecycle_status,
            policy_id=POLICY_ID,
            control_id=CONTROL_ID,
            scope=PolicyExceptionScope.CONTROL,
            reason="Rejected waiver request.",
            requested_by="operator@example.test",
            requested_on=_dt(9, 10),
            decided_by="approver@example.test",
            decided_on=_dt(9, 11),
            decision_reference="CAB-REJECT-001",
        )

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=exception,
        evaluated_at=_dt(10, 12),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.NOT_APPROVED
    )

    assert result.effective_requirement_ids == ()


def test_future_approved_waiver_is_not_yet_effective() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(10, 8),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.NOT_YET_EFFECTIVE
    )

    assert result.effective_requirement_ids == ()


def test_valid_from_boundary_is_inclusive() -> None:
    waiver = _approved_control_waiver()

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=waiver,
        evaluated_at=waiver.valid_from,
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EFFECTIVE
    )


def test_valid_to_boundary_is_inclusive() -> None:
    waiver = _approved_control_waiver()

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(
            evaluated_on=date(2026, 6, 11),
        ),
        exception=waiver,
        evaluated_at=waiver.valid_to,
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EFFECTIVE
    )


def test_waiver_after_validity_window_is_expired() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(
            evaluated_on=date(2026, 6, 11),
        ),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(11, 2),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EXPIRED
    )

    assert result.effective_requirement_ids == ()


def test_revoked_waiver_is_historically_effective_before_revocation() -> None:
    approved = _approved_control_waiver()

    revoked = PolicyException(
        **{
            **approved.model_dump(),
            "status": PolicyExceptionStatus.REVOKED,
            "revoked_by": "approver@example.test",
            "revoked_on": _dt(10, 18),
            "revocation_reason": (
                "Temporary deviation no longer required."
            ),
        }
    )

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=revoked,
        evaluated_at=_dt(10, 16),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EFFECTIVE
    )


def test_revocation_boundary_is_inclusive() -> None:
    approved = _approved_control_waiver()

    revoked = PolicyException(
        **{
            **approved.model_dump(),
            "status": PolicyExceptionStatus.REVOKED,
            "revoked_by": "approver@example.test",
            "revoked_on": _dt(10, 18),
            "revocation_reason": (
                "Temporary deviation no longer required."
            ),
        }
    )

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=revoked,
        evaluated_at=_dt(10, 18),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.REVOKED
    )

    assert result.effective_requirement_ids == ()


@pytest.mark.parametrize(
    "activation_status",
    [
        ControlActivationStatus.NOT_YET_EFFECTIVE,
        ControlActivationStatus.EXPIRED,
        ControlActivationStatus.NOT_APPLICABLE,
        ControlActivationStatus.INDETERMINATE,
    ],
)
def test_effective_window_cannot_waive_inactive_control(
    activation_status: ControlActivationStatus,
) -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(
            status=activation_status,
        ),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(10, 12),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.TARGET_NOT_ACTIVE
    )

    assert result.effective_requirement_ids == ()


def test_unknown_policy_is_configuration_error() -> None:
    exception = _approved_control_waiver().model_copy(
        update={
            "policy_id": "POL-UNKNOWN",
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(),
            exception=exception,
            evaluated_at=_dt(10, 12),
        )


def test_unknown_control_is_configuration_error() -> None:
    exception = _approved_control_waiver().model_copy(
        update={
            "control_id": "CTRL-UNKNOWN",
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(),
            exception=exception,
            evaluated_at=_dt(10, 12),
        )


def test_control_must_belong_to_exception_policy() -> None:
    exception = _approved_control_waiver().model_copy(
        update={
            "policy_id": OTHER_POLICY_ID,
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(
                policy_id=OTHER_POLICY_ID,
            ),
            exception=exception,
            evaluated_at=_dt(10, 12),
        )


def test_requirement_scope_must_reference_control_requirement() -> None:
    exception = _approved_requirement_waiver().model_copy(
        update={
            "requirement_ids": (
                "REQ-NOT-IN-CONTROL",
            ),
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(),
            exception=exception,
            evaluated_at=_dt(10, 12),
        )


def test_activation_policy_identity_must_match_exception() -> None:
    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(
                policy_id=OTHER_POLICY_ID,
            ),
            exception=_approved_control_waiver(),
            evaluated_at=_dt(10, 12),
        )


def test_activation_control_identity_must_match_exception() -> None:
    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(
                control_id="CTRL-OTHER",
            ),
            exception=_approved_control_waiver(),
            evaluated_at=_dt(10, 12),
        )


def test_activation_date_must_match_evaluation_date() -> None:
    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(
                evaluated_on=date(2026, 6, 9),
            ),
            exception=_approved_control_waiver(),
            evaluated_at=_dt(10, 12),
        )


def test_evaluation_timestamp_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=_activation(),
            exception=_approved_control_waiver(),
            evaluated_at=datetime(
                2026,
                6,
                10,
                12,
            ),
        )


def test_resolution_preserves_audit_identity() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(10, 12),
    )

    assert result.exception_id == "EXC-CONTROL-001"
    assert result.policy_id == POLICY_ID
    assert result.control_id == CONTROL_ID
    assert result.evaluated_at == _dt(10, 12)

    assert (
        result.exception_status
        == PolicyExceptionStatus.APPROVED
    )


def test_resolution_result_is_frozen() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(10, 12),
    )

    with pytest.raises(Exception):
        result.status = (
            PolicyExceptionResolutionStatus.EXPIRED
        )


def test_resolution_does_not_model_compliance_or_decisions() -> None:
    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(),
        exception=_approved_control_waiver(),
        evaluated_at=_dt(10, 12),
    )

    fields = result.model_fields

    assert "compliance" not in fields
    assert "blocking" not in fields
    assert "decision" not in fields
    assert "action" not in fields
    assert "outcome" not in fields
    assert "requirement_assessments" not in fields

def test_expired_state_precedes_later_revocation() -> None:
    approved = _approved_control_waiver()

    revoked = PolicyException(
        **{
            **approved.model_dump(),
            "status": PolicyExceptionStatus.REVOKED,
            "revoked_by": "approver@example.test",
            "revoked_on": _dt(11, 2),
            "revocation_reason": (
                "Administrative closure after natural expiry."
            ),
        }
    )

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(
            evaluated_on=date(2026, 6, 11),
        ),
        exception=revoked,
        evaluated_at=_dt(11, 3),
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.EXPIRED
    )

    assert (
        result.exception_status
        == PolicyExceptionStatus.REVOKED
    )

    assert result.effective_requirement_ids == ()


def test_revocation_at_valid_to_boundary_is_revoked() -> None:
    approved = _approved_control_waiver()

    revoked = PolicyException(
        **{
            **approved.model_dump(),
            "status": PolicyExceptionStatus.REVOKED,
            "revoked_by": "approver@example.test",
            "revoked_on": approved.valid_to,
            "revocation_reason": (
                "Waiver revoked at final valid instant."
            ),
        }
    )

    result = resolve_policy_exception(
        catalogue=_catalogue(),
        activation=_activation(
            evaluated_on=date(2026, 6, 11),
        ),
        exception=revoked,
        evaluated_at=approved.valid_to,
    )

    assert (
        result.status
        == PolicyExceptionResolutionStatus.REVOKED
    )

    assert result.effective_requirement_ids == ()


def test_active_activation_rejects_reordered_requirements() -> None:
    activation = _activation().model_copy(
        update={
            "active_requirement_ids": (
                REQ_TRANSACTION,
                REQ_SMOKE,
            ),
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=activation,
            exception=_approved_control_waiver(),
            evaluated_at=_dt(10, 12),
        )


def test_active_activation_rejects_missing_requirements() -> None:
    activation = _activation().model_copy(
        update={
            "active_requirement_ids": (
                REQ_SMOKE,
            ),
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=activation,
            exception=_approved_control_waiver(),
            evaluated_at=_dt(10, 12),
        )


def test_inactive_activation_rejects_exposed_requirements() -> None:
    activation = _activation(
        status=ControlActivationStatus.NOT_APPLICABLE,
    ).model_copy(
        update={
            "active_requirement_ids": (
                REQ_SMOKE,
                REQ_TRANSACTION,
            ),
        }
    )

    with pytest.raises(ValueError):
        resolve_policy_exception(
            catalogue=_catalogue(),
            activation=activation,
            exception=_approved_control_waiver(),
            evaluated_at=_dt(10, 12),
        )
