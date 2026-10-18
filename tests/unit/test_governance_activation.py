from __future__ import annotations

from datetime import date

import pytest

from synthetic_ops_generator.governance.activation import (
    ControlActivationStatus,
    resolve_control_activation,
)
from synthetic_ops_generator.governance.applicability import (
    ControlApplicabilityResult,
    ControlApplicabilityStatus,
)
from synthetic_ops_generator.governance.models import (
    PolicyApplicability,
    PolicyControl,
    PolicyDocument,
)


def _policy(
    *,
    effective_from: date = date(2026, 1, 1),
    effective_to: date | None = date(2026, 12, 31),
) -> PolicyDocument:
    return PolicyDocument(
        policy_id="POL-CHANGE-0042",
        title="Enterprise Change Management Standard",
        version="4.2",
        owner="Enterprise Change Management",
        authority_id="AUTH-CHANGE-MGMT",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _control() -> PolicyControl:
    return PolicyControl(
        control_id="CTRL-POST-CHANGE-VALIDATION",
        policy_id="POL-CHANGE-0042",
        control_reference="4.2.3",
        title="Production post-change validation",
        objective=(
            "Require validation for applicable "
            "production changes."
        ),
        applicability=PolicyApplicability(),
        requirement_ids=(
            "REQ-SMOKE-001",
            "REQ-TRANSACTION-001",
        ),
    )


def _applicability(
    status: ControlApplicabilityStatus,
) -> ControlApplicabilityResult:
    return ControlApplicabilityResult(
        control_id="CTRL-POST-CHANGE-VALIDATION",
        status=status,
        evaluated_dimensions={},
    )


def test_effective_applicable_control_is_active() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert result.status == ControlActivationStatus.ACTIVE

    assert result.active_requirement_ids == (
        "REQ-SMOKE-001",
        "REQ-TRANSACTION-001",
    )


def test_effective_from_boundary_is_inclusive() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 1, 1),
    )

    assert result.status == ControlActivationStatus.ACTIVE


def test_effective_to_boundary_is_inclusive() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 12, 31),
    )

    assert result.status == ControlActivationStatus.ACTIVE


def test_before_effective_period_is_not_yet_effective() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2025, 12, 31),
    )

    assert (
        result.status
        == ControlActivationStatus.NOT_YET_EFFECTIVE
    )

    assert result.active_requirement_ids == ()


def test_after_effective_period_is_expired() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2027, 1, 1),
    )

    assert result.status == ControlActivationStatus.EXPIRED

    assert result.active_requirement_ids == ()


def test_open_ended_policy_remains_effective() -> None:
    result = resolve_control_activation(
        policy=_policy(
            effective_to=None,
        ),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2030, 1, 1),
    )

    assert result.status == ControlActivationStatus.ACTIVE


def test_effective_but_not_applicable_control_is_not_applicable() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.NOT_APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert (
        result.status
        == ControlActivationStatus.NOT_APPLICABLE
    )

    assert result.active_requirement_ids == ()


def test_effective_indeterminate_control_remains_indeterminate() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.INDETERMINATE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert (
        result.status
        == ControlActivationStatus.INDETERMINATE
    )

    assert result.active_requirement_ids == ()


def test_temporal_state_precedes_applicability_state() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.INDETERMINATE
        ),
        evaluated_on=date(2027, 1, 1),
    )

    assert result.status == ControlActivationStatus.EXPIRED


def test_result_preserves_policy_control_and_date_identity() -> None:
    evaluated_on = date(2026, 6, 15)

    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=evaluated_on,
    )

    assert result.policy_id == "POL-CHANGE-0042"
    assert (
        result.control_id
        == "CTRL-POST-CHANGE-VALIDATION"
    )
    assert result.evaluated_on == evaluated_on


def test_result_preserves_applicability_status() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert (
        result.applicability_status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_control_must_belong_to_policy() -> None:
    control = _control().model_copy(
        update={
            "policy_id": "POL-OTHER",
        }
    )

    with pytest.raises(ValueError):
        resolve_control_activation(
            policy=_policy(),
            control=control,
            applicability=_applicability(
                ControlApplicabilityStatus.APPLICABLE
            ),
            evaluated_on=date(2026, 6, 15),
        )


def test_applicability_result_must_belong_to_control() -> None:
    applicability = _applicability(
        ControlApplicabilityStatus.APPLICABLE
    ).model_copy(
        update={
            "control_id": "CTRL-OTHER",
        }
    )

    with pytest.raises(ValueError):
        resolve_control_activation(
            policy=_policy(),
            control=_control(),
            applicability=applicability,
            evaluated_on=date(2026, 6, 15),
        )


def test_activation_does_not_recompute_applicability() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.NOT_APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert (
        result.status
        == ControlActivationStatus.NOT_APPLICABLE
    )


def test_activation_result_does_not_model_enforcement() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    fields = result.model_fields

    assert "blocking" not in fields
    assert "decision" not in fields
    assert "action" not in fields
    assert "outcome" not in fields
    assert "waived" not in fields
    assert "exception" not in fields


def test_activation_does_not_assess_requirement_evidence() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    fields = result.model_fields

    assert "requirement_assessments" not in fields
    assert "evidence" not in fields
    assert "compliance" not in fields

def test_active_requirement_order_is_preserved() -> None:
    control = _control().model_copy(
        update={
            "requirement_ids": (
                "REQ-FIRST",
                "REQ-SECOND",
                "REQ-THIRD",
            ),
        }
    )

    result = resolve_control_activation(
        policy=_policy(),
        control=control,
        applicability=ControlApplicabilityResult(
            control_id=control.control_id,
            status=ControlApplicabilityStatus.APPLICABLE,
            evaluated_dimensions={},
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert result.active_requirement_ids == (
        "REQ-FIRST",
        "REQ-SECOND",
        "REQ-THIRD",
    )


def test_not_applicable_never_exposes_requirements() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.NOT_APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert result.active_requirement_ids == ()


def test_indeterminate_never_exposes_requirements() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.INDETERMINATE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    assert result.active_requirement_ids == ()


def test_not_yet_effective_precedes_not_applicable() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.NOT_APPLICABLE
        ),
        evaluated_on=date(2025, 12, 31),
    )

    assert (
        result.status
        == ControlActivationStatus.NOT_YET_EFFECTIVE
    )


def test_activation_result_is_frozen() -> None:
    result = resolve_control_activation(
        policy=_policy(),
        control=_control(),
        applicability=_applicability(
            ControlApplicabilityStatus.APPLICABLE
        ),
        evaluated_on=date(2026, 6, 15),
    )

    with pytest.raises(Exception):
        result.status = ControlActivationStatus.EXPIRED

