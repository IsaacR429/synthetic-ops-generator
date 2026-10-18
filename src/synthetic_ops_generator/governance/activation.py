from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from synthetic_ops_generator.governance.applicability import (
    ControlApplicabilityResult,
    ControlApplicabilityStatus,
)
from synthetic_ops_generator.governance.models import (
    PolicyControl,
    PolicyDocument,
)


class ControlActivationStatus(StrEnum):
    """
    Effective activation state of one PolicyControl.

    Activation combines policy temporal validity with an already
    resolved contextual applicability result.

    It does not assess evidence, compliance, blocking, waivers,
    exceptions, or runtime decisions.
    """

    ACTIVE = "active"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"
    NOT_APPLICABLE = "not_applicable"
    INDETERMINATE = "indeterminate"


class ControlActivationResult(BaseModel):
    """
    Auditable result of resolving one control's current activation.

    active_requirement_ids are exposed only when the control is both
    temporally effective and contextually applicable.
    """

    model_config = ConfigDict(frozen=True)

    policy_id: str
    control_id: str

    evaluated_on: date

    applicability_status: ControlApplicabilityStatus
    status: ControlActivationStatus

    active_requirement_ids: tuple[str, ...] = ()


def resolve_control_activation(
    *,
    policy: PolicyDocument,
    control: PolicyControl,
    applicability: ControlApplicabilityResult,
    evaluated_on: date,
) -> ControlActivationResult:
    """
    Resolve temporal validity plus previously resolved applicability.

    Precedence:
      1. before effective_from -> NOT_YET_EFFECTIVE
      2. after effective_to -> EXPIRED
      3. applicability NOT_APPLICABLE -> NOT_APPLICABLE
      4. applicability INDETERMINATE -> INDETERMINATE
      5. applicability APPLICABLE -> ACTIVE

    Policy effective boundaries are inclusive.
    """

    if control.policy_id != policy.policy_id:
        raise ValueError(
            "Policy Control does not belong to PolicyDocument: "
            f"{control.control_id} -> {control.policy_id}, "
            f"expected {policy.policy_id}."
        )

    if applicability.control_id != control.control_id:
        raise ValueError(
            "Applicability result does not belong to PolicyControl: "
            f"{applicability.control_id}, "
            f"expected {control.control_id}."
        )

    if evaluated_on < policy.effective_from:
        status = (
            ControlActivationStatus.NOT_YET_EFFECTIVE
        )
        active_requirement_ids: tuple[str, ...] = ()

    elif (
        policy.effective_to is not None
        and evaluated_on > policy.effective_to
    ):
        status = ControlActivationStatus.EXPIRED
        active_requirement_ids = ()

    elif (
        applicability.status
        == ControlApplicabilityStatus.NOT_APPLICABLE
    ):
        status = ControlActivationStatus.NOT_APPLICABLE
        active_requirement_ids = ()

    elif (
        applicability.status
        == ControlApplicabilityStatus.INDETERMINATE
    ):
        status = ControlActivationStatus.INDETERMINATE
        active_requirement_ids = ()

    elif (
        applicability.status
        == ControlApplicabilityStatus.APPLICABLE
    ):
        status = ControlActivationStatus.ACTIVE
        active_requirement_ids = control.requirement_ids

    else:
        raise ValueError(
            "Unsupported Control applicability status: "
            f"{applicability.status}"
        )

    return ControlActivationResult(
        policy_id=policy.policy_id,
        control_id=control.control_id,
        evaluated_on=evaluated_on,
        applicability_status=applicability.status,
        status=status,
        active_requirement_ids=active_requirement_ids,
    )
