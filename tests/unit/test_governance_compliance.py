from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from synthetic_ops_generator.checks.assessment import (
    RequirementAssessment,
    RequirementAssessmentStatus,
    RequirementEvidenceScope,
)
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
from synthetic_ops_generator.governance.compliance import (
    ControlGovernanceStatus,
    assess_control_governance,
)
from synthetic_ops_generator.governance.exception_resolution import (
    PolicyExceptionResolution,
    PolicyExceptionResolutionStatus,
)
from synthetic_ops_generator.governance.exceptions import (
    PolicyExceptionStatus,
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
CONTROL_ID = "CTRL-POST-CHANGE-VALIDATION"

REQ_SMOKE = "REQ-SMOKE-001"
REQ_TRANSACTION = "REQ-TRANSACTION-001"
REQ_DOCUMENT = "REQ-DOCUMENT-001"

CHECK_SMOKE = "application.post_deployment_smoke"
CHECK_TRANSACTION = "application.transaction_processing"
CHECK_DOCUMENT = "application.functional_validation"


def _dt(
    day: int = 10,
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
    *,
    requirement_id: str,
    check_definition_id: str,
    obligation: RequirementObligation,
) -> CheckRequirement:
    return CheckRequirement(
        requirement_id=requirement_id,
        check_definition_id=check_definition_id,
        obligation=obligation,
        rationale="Enterprise assurance requirement.",
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

    requirements = {
        REQ_SMOKE: _requirement(
            requirement_id=REQ_SMOKE,
            check_definition_id=CHECK_SMOKE,
            obligation=RequirementObligation.REQUIRED,
        ),
        REQ_TRANSACTION: _requirement(
            requirement_id=REQ_TRANSACTION,
            check_definition_id=CHECK_TRANSACTION,
            obligation=RequirementObligation.REQUIRED,
        ),
        REQ_DOCUMENT: _requirement(
            requirement_id=REQ_DOCUMENT,
            check_definition_id=CHECK_DOCUMENT,
            obligation=RequirementObligation.RECOMMENDED,
        ),
    }

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
            REQ_DOCUMENT,
        ),
    )

    return PolicyCatalogue(
        authorities={
            authority.authority_id: authority,
        },
        policies={
            policy.policy_id: policy,
        },
        controls={
            control.control_id: control,
        },
        requirements=requirements,
    )


def _scope() -> RequirementEvidenceScope:
    return RequirementEvidenceScope(
        run_id="RUN-001",
        service="claims-processing",
        environment="production",
        chg_id="CHG-2026-001",
    )


def _assessment(
    requirement_id: str,
    status: RequirementAssessmentStatus,
) -> RequirementAssessment:
    catalogue = _catalogue()
    requirement = catalogue.requirements[requirement_id]

    return RequirementAssessment(
        requirement_id=requirement.requirement_id,
        check_definition_id=requirement.check_definition_id,
        obligation=requirement.obligation,
        status=status,
        scope=_scope(),
    )


def _all_satisfied() -> tuple[RequirementAssessment, ...]:
    return (
        _assessment(
            REQ_SMOKE,
            RequirementAssessmentStatus.SATISFIED,
        ),
        _assessment(
            REQ_TRANSACTION,
            RequirementAssessmentStatus.SATISFIED,
        ),
        _assessment(
            REQ_DOCUMENT,
            RequirementAssessmentStatus.SATISFIED,
        ),
    )


def _activation(
    *,
    status: ControlActivationStatus = (
        ControlActivationStatus.ACTIVE
    ),
    evaluated_on: date = date(2026, 6, 10),
) -> ControlActivationResult:
    if status == ControlActivationStatus.ACTIVE:
        active_requirement_ids = (
            REQ_SMOKE,
            REQ_TRANSACTION,
            REQ_DOCUMENT,
        )
        applicability_status = (
            ControlApplicabilityStatus.APPLICABLE
        )

    elif (
        status
        == ControlActivationStatus.NOT_APPLICABLE
    ):
        active_requirement_ids = ()
        applicability_status = (
            ControlApplicabilityStatus.NOT_APPLICABLE
        )

    elif (
        status
        == ControlActivationStatus.INDETERMINATE
    ):
        active_requirement_ids = ()
        applicability_status = (
            ControlApplicabilityStatus.INDETERMINATE
        )

    else:
        active_requirement_ids = ()
        applicability_status = (
            ControlApplicabilityStatus.APPLICABLE
        )

    return ControlActivationResult(
        policy_id=POLICY_ID,
        control_id=CONTROL_ID,
        evaluated_on=evaluated_on,
        applicability_status=applicability_status,
        status=status,
        active_requirement_ids=active_requirement_ids,
    )


def _exception_resolution(
    *,
    exception_id: str = "EXC-001",
    status: PolicyExceptionResolutionStatus = (
        PolicyExceptionResolutionStatus.EFFECTIVE
    ),
    requirement_ids: tuple[str, ...] = (
        REQ_TRANSACTION,
    ),
    evaluated_at: datetime = _dt(),
) -> PolicyExceptionResolution:
    if (
        status
        == PolicyExceptionResolutionStatus.REVOKED
    ):
        exception_status = PolicyExceptionStatus.REVOKED
    elif (
        status
        == PolicyExceptionResolutionStatus.NOT_APPROVED
    ):
        exception_status = PolicyExceptionStatus.REQUESTED
    else:
        exception_status = PolicyExceptionStatus.APPROVED

    return PolicyExceptionResolution(
        exception_id=exception_id,
        policy_id=POLICY_ID,
        control_id=CONTROL_ID,
        evaluated_at=evaluated_at,
        exception_status=exception_status,
        activation_status=ControlActivationStatus.ACTIVE,
        status=status,
        effective_requirement_ids=(
            requirement_ids
            if status
            == PolicyExceptionResolutionStatus.EFFECTIVE
            else ()
        ),
    )


def _assess(
    *,
    assessments: tuple[RequirementAssessment, ...],
    exceptions: tuple[
        PolicyExceptionResolution,
        ...,
    ] = (),
    activation: ControlActivationResult | None = None,
    evaluated_at: datetime = _dt(),
):
    return assess_control_governance(
        catalogue=_catalogue(),
        activation=(
            activation
            if activation is not None
            else _activation()
        ),
        requirement_assessments=assessments,
        exception_resolutions=exceptions,
        evaluated_at=evaluated_at,
    )


def test_all_required_requirements_satisfied_is_compliant() -> None:
    result = _assess(
        assessments=_all_satisfied(),
    )

    assert (
        result.status
        == ControlGovernanceStatus.COMPLIANT
    )

    assert result.failed_requirement_ids == ()
    assert result.missing_requirement_ids == ()
    assert result.insufficient_requirement_ids == ()
    assert result.excepted_requirement_ids == ()


def test_failed_required_requirement_is_non_compliant() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.FAILED,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.NON_COMPLIANT
    )

    assert result.failed_requirement_ids == (
        REQ_TRANSACTION,
    )

    assert (
        result.unexcepted_required_requirement_ids
        == (REQ_TRANSACTION,)
    )


def test_missing_required_requirement_is_incomplete() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.MISSING,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.INCOMPLETE
    )

    assert result.missing_requirement_ids == (
        REQ_TRANSACTION,
    )


def test_insufficient_required_requirement_is_incomplete() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.INSUFFICIENT,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.INCOMPLETE
    )

    assert result.insufficient_requirement_ids == (
        REQ_SMOKE,
    )


def test_failed_required_requirement_precedes_missing() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.FAILED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.MISSING,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.NON_COMPLIANT
    )

    assert result.failed_requirement_ids == (
        REQ_SMOKE,
    )

    assert result.missing_requirement_ids == (
        REQ_TRANSACTION,
    )


@pytest.mark.parametrize(
    "factual_status",
    [
        RequirementAssessmentStatus.FAILED,
        RequirementAssessmentStatus.MISSING,
        RequirementAssessmentStatus.INSUFFICIENT,
    ],
)
def test_effective_exception_excepted_required_issue(
    factual_status: RequirementAssessmentStatus,
) -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_TRANSACTION,
                factual_status,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
        exceptions=(
            _exception_resolution(),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.EXCEPTED
    )

    assert result.excepted_requirement_ids == (
        REQ_TRANSACTION,
    )

    assert (
        result.unexcepted_required_requirement_ids
        == ()
    )

    assert result.effective_exception_ids == (
        "EXC-001",
    )


def test_partial_exception_does_not_hide_unwaived_failure() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.FAILED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.MISSING,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
        exceptions=(
            _exception_resolution(
                requirement_ids=(
                    REQ_TRANSACTION,
                ),
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.NON_COMPLIANT
    )

    assert result.excepted_requirement_ids == (
        REQ_TRANSACTION,
    )

    assert (
        result.unexcepted_required_requirement_ids
        == (REQ_SMOKE,)
    )


def test_partial_exception_leaving_missing_requirement_is_incomplete() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.FAILED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.MISSING,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
        exceptions=(
            _exception_resolution(
                requirement_ids=(
                    REQ_SMOKE,
                ),
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.INCOMPLETE
    )

    assert (
        result.unexcepted_required_requirement_ids
        == (REQ_TRANSACTION,)
    )


def test_exception_on_satisfied_requirement_does_not_force_excepted() -> None:
    result = _assess(
        assessments=_all_satisfied(),
        exceptions=(
            _exception_resolution(),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.COMPLIANT
    )

    assert result.excepted_requirement_ids == ()

    assert result.effective_exception_ids == (
        "EXC-001",
    )


@pytest.mark.parametrize(
    "factual_status",
    [
        RequirementAssessmentStatus.FAILED,
        RequirementAssessmentStatus.MISSING,
        RequirementAssessmentStatus.INSUFFICIENT,
    ],
)
def test_recommended_issue_is_advisory_not_non_compliant(
    factual_status: RequirementAssessmentStatus,
) -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_DOCUMENT,
                factual_status,
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.COMPLIANT
    )

    assert result.advisory_requirement_ids == (
        REQ_DOCUMENT,
    )

    assert (
        result.unexcepted_required_requirement_ids
        == ()
    )


def test_effective_exception_can_cover_recommended_issue_without_changing_compliance() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.MISSING,
            ),
        ),
        exceptions=(
            _exception_resolution(
                requirement_ids=(
                    REQ_DOCUMENT,
                ),
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.COMPLIANT
    )

    assert result.excepted_requirement_ids == (
        REQ_DOCUMENT,
    )

    assert result.advisory_requirement_ids == ()


@pytest.mark.parametrize(
    "exception_status",
    [
        PolicyExceptionResolutionStatus.NOT_APPROVED,
        PolicyExceptionResolutionStatus.NOT_YET_EFFECTIVE,
        PolicyExceptionResolutionStatus.EXPIRED,
        PolicyExceptionResolutionStatus.REVOKED,
        PolicyExceptionResolutionStatus.TARGET_NOT_ACTIVE,
    ],
)
def test_non_effective_exception_does_not_except_requirement(
    exception_status: PolicyExceptionResolutionStatus,
) -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.SATISFIED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.FAILED,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
        exceptions=(
            _exception_resolution(
                status=exception_status,
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.NON_COMPLIANT
    )

    assert result.excepted_requirement_ids == ()
    assert result.effective_exception_ids == ()


def test_not_applicable_control_is_not_applicable() -> None:
    result = _assess(
        assessments=(),
        activation=_activation(
            status=ControlActivationStatus.NOT_APPLICABLE,
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.NOT_APPLICABLE
    )


def test_indeterminate_activation_is_indeterminate() -> None:
    result = _assess(
        assessments=(),
        activation=_activation(
            status=ControlActivationStatus.INDETERMINATE,
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.INDETERMINATE
    )


@pytest.mark.parametrize(
    "activation_status",
    [
        ControlActivationStatus.NOT_YET_EFFECTIVE,
        ControlActivationStatus.EXPIRED,
    ],
)
def test_temporally_inactive_control_is_not_in_effect(
    activation_status: ControlActivationStatus,
) -> None:
    result = _assess(
        assessments=(),
        activation=_activation(
            status=activation_status,
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.NOT_IN_EFFECT
    )


def test_missing_assessment_object_is_configuration_error() -> None:
    with pytest.raises(ValueError):
        _assess(
            assessments=(
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
        )


def test_duplicate_requirement_assessment_is_configuration_error() -> None:
    with pytest.raises(ValueError):
        _assess(
            assessments=(
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_TRANSACTION,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
        )


def test_assessment_for_unknown_requirement_is_configuration_error() -> None:
    invalid = _assessment(
        REQ_SMOKE,
        RequirementAssessmentStatus.SATISFIED,
    ).model_copy(
        update={
            "requirement_id": "REQ-UNKNOWN",
        }
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=(
                invalid,
                _assessment(
                    REQ_TRANSACTION,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
        )


def test_assessment_check_definition_identity_must_match() -> None:
    invalid = _assessment(
        REQ_SMOKE,
        RequirementAssessmentStatus.SATISFIED,
    ).model_copy(
        update={
            "check_definition_id": CHECK_TRANSACTION,
        }
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=(
                invalid,
                _assessment(
                    REQ_TRANSACTION,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
        )


def test_assessment_obligation_identity_must_match() -> None:
    invalid = _assessment(
        REQ_SMOKE,
        RequirementAssessmentStatus.SATISFIED,
    ).model_copy(
        update={
            "obligation": RequirementObligation.RECOMMENDED,
        }
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=(
                invalid,
                _assessment(
                    REQ_TRANSACTION,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
        )


def test_activation_requirement_set_must_match_control() -> None:
    activation = _activation().model_copy(
        update={
            "active_requirement_ids": (
                REQ_SMOKE,
                REQ_TRANSACTION,
            ),
        }
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=(
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                _assessment(
                    REQ_TRANSACTION,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
            activation=activation,
        )


def test_exception_resolution_target_must_match_control() -> None:
    exception = _exception_resolution().model_copy(
        update={
            "control_id": "CTRL-OTHER",
        }
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=_all_satisfied(),
            exceptions=(exception,),
        )


def test_exception_resolution_evaluation_instant_must_match() -> None:
    exception = _exception_resolution(
        evaluated_at=_dt(10, 11),
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=_all_satisfied(),
            exceptions=(exception,),
            evaluated_at=_dt(10, 12),
        )


def test_evaluated_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError):
        _assess(
            assessments=_all_satisfied(),
            evaluated_at=datetime(
                2026,
                6,
                10,
                12,
            ),
        )


def test_activation_date_must_match_governance_evaluation_date() -> None:
    with pytest.raises(ValueError):
        _assess(
            assessments=_all_satisfied(),
            activation=_activation(
                evaluated_on=date(2026, 6, 9),
            ),
            evaluated_at=_dt(10, 12),
        )


def test_governance_assessment_preserves_audit_identity() -> None:
    result = _assess(
        assessments=_all_satisfied(),
    )

    assert result.policy_id == POLICY_ID
    assert result.control_id == CONTROL_ID
    assert result.evaluated_at == _dt()
    assert (
        result.activation_status
        == ControlActivationStatus.ACTIVE
    )


def test_governance_assessment_is_frozen_and_has_no_runtime_decision_fields() -> None:
    result = _assess(
        assessments=_all_satisfied(),
    )

    with pytest.raises(Exception):
        result.status = (
            ControlGovernanceStatus.NON_COMPLIANT
        )

    fields = result.model_fields

    assert "blocking" not in fields
    assert "readiness" not in fields
    assert "decision" not in fields
    assert "action" not in fields
    assert "outcome" not in fields
    assert "recommended_action" not in fields

def test_requirement_assessments_must_share_scope() -> None:
    different_scope = _assessment(
        REQ_TRANSACTION,
        RequirementAssessmentStatus.SATISFIED,
    ).model_copy(
        update={
            "scope": RequirementEvidenceScope(
                run_id="RUN-002",
                service="claims-processing",
                environment="production",
                chg_id="CHG-2026-002",
            )
        }
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=(
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.SATISFIED,
                ),
                different_scope,
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
        )


def test_inactive_control_rejects_requirement_assessments() -> None:
    with pytest.raises(ValueError):
        _assess(
            assessments=(
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
            activation=_activation(
                status=ControlActivationStatus.NOT_APPLICABLE,
            ),
        )


def test_duplicate_exception_resolution_identity_is_rejected() -> None:
    first = _exception_resolution(
        exception_id="EXC-DUPLICATE",
        requirement_ids=(
            REQ_SMOKE,
        ),
    )

    second = _exception_resolution(
        exception_id="EXC-DUPLICATE",
        requirement_ids=(
            REQ_TRANSACTION,
        ),
    )

    with pytest.raises(ValueError):
        _assess(
            assessments=(
                _assessment(
                    REQ_SMOKE,
                    RequirementAssessmentStatus.FAILED,
                ),
                _assessment(
                    REQ_TRANSACTION,
                    RequirementAssessmentStatus.MISSING,
                ),
                _assessment(
                    REQ_DOCUMENT,
                    RequirementAssessmentStatus.SATISFIED,
                ),
            ),
            exceptions=(
                first,
                second,
            ),
        )


def test_output_order_follows_control_requirement_order() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.INSUFFICIENT,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.MISSING,
            ),
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.FAILED,
            ),
        ),
    )

    assert result.failed_requirement_ids == (
        REQ_SMOKE,
    )

    assert result.missing_requirement_ids == (
        REQ_TRANSACTION,
    )

    assert result.insufficient_requirement_ids == (
        REQ_DOCUMENT,
    )


def test_multiple_effective_exceptions_can_cover_distinct_required_issues() -> None:
    result = _assess(
        assessments=(
            _assessment(
                REQ_SMOKE,
                RequirementAssessmentStatus.FAILED,
            ),
            _assessment(
                REQ_TRANSACTION,
                RequirementAssessmentStatus.MISSING,
            ),
            _assessment(
                REQ_DOCUMENT,
                RequirementAssessmentStatus.SATISFIED,
            ),
        ),
        exceptions=(
            _exception_resolution(
                exception_id="EXC-SMOKE",
                requirement_ids=(
                    REQ_SMOKE,
                ),
            ),
            _exception_resolution(
                exception_id="EXC-TRANSACTION",
                requirement_ids=(
                    REQ_TRANSACTION,
                ),
            ),
        ),
    )

    assert (
        result.status
        == ControlGovernanceStatus.EXCEPTED
    )

    assert result.excepted_requirement_ids == (
        REQ_SMOKE,
        REQ_TRANSACTION,
    )

    assert (
        result.unexcepted_required_requirement_ids
        == ()
    )

    assert result.effective_exception_ids == (
        "EXC-SMOKE",
        "EXC-TRANSACTION",
    )
