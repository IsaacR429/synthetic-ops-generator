from datetime import datetime
from enum import StrEnum
from typing import Iterable

from pydantic import BaseModel, ConfigDict

from synthetic_ops_generator.checks.assessment import (
    RequirementAssessment,
    RequirementAssessmentStatus,
)
from synthetic_ops_generator.checks.requirements import (
    RequirementObligation,
)
from synthetic_ops_generator.governance.activation import (
    ControlActivationResult,
    ControlActivationStatus,
)
from synthetic_ops_generator.governance.exception_resolution import (
    PolicyExceptionResolution,
    PolicyExceptionResolutionStatus,
)
from synthetic_ops_generator.governance.models import (
    PolicyCatalogue,
)


class ControlGovernanceStatus(StrEnum):
    """
    Governance interpretation of one enterprise control.

    This status combines already-resolved control activation,
    factual requirement assessments, obligation strength, and
    already-resolved policy exceptions.

    It does not determine runtime blocking, readiness, Go/No-Go,
    remediation, Decision, Action, or Outcome.
    """

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    INCOMPLETE = "incomplete"
    EXCEPTED = "excepted"
    NOT_IN_EFFECT = "not_in_effect"
    NOT_APPLICABLE = "not_applicable"
    INDETERMINATE = "indeterminate"


class ControlGovernanceAssessment(BaseModel):
    """
    Auditable governance interpretation for one PolicyControl.

    Factual assessment states remain visible even when an effective
    exception covers a requirement. Exception coverage therefore does
    not rewrite FAILED, MISSING, or INSUFFICIENT evidence as SATISFIED.
    """

    model_config = ConfigDict(frozen=True)

    policy_id: str
    control_id: str
    evaluated_at: datetime

    activation_status: ControlActivationStatus
    status: ControlGovernanceStatus

    failed_requirement_ids: tuple[str, ...] = ()
    missing_requirement_ids: tuple[str, ...] = ()
    insufficient_requirement_ids: tuple[str, ...] = ()

    excepted_requirement_ids: tuple[str, ...] = ()
    advisory_requirement_ids: tuple[str, ...] = ()

    unexcepted_required_requirement_ids: tuple[str, ...] = ()

    effective_exception_ids: tuple[str, ...] = ()


def _validate_evaluated_at(
    evaluated_at: datetime,
) -> None:
    if (
        evaluated_at.tzinfo is None
        or evaluated_at.utcoffset() is None
    ):
        raise ValueError(
            "Control governance assessment requires a "
            "timezone-aware evaluated_at timestamp."
        )


def _validate_activation(
    *,
    catalogue: PolicyCatalogue,
    activation: ControlActivationResult,
    evaluated_at: datetime,
) -> None:
    policy = catalogue.policies.get(
        activation.policy_id
    )

    if policy is None:
        raise ValueError(
            "Control activation references unknown policy: "
            f"{activation.policy_id}."
        )

    control = catalogue.controls.get(
        activation.control_id
    )

    if control is None:
        raise ValueError(
            "Control activation references unknown control: "
            f"{activation.control_id}."
        )

    if control.policy_id != activation.policy_id:
        raise ValueError(
            "Control activation policy identity does not "
            "match the control catalogue relationship: "
            f"{activation.control_id} -> "
            f"{control.policy_id}, expected "
            f"{activation.policy_id}."
        )

    if activation.evaluated_on != evaluated_at.date():
        raise ValueError(
            "Control activation evaluation date does not "
            "match governance evaluation date: "
            f"{activation.evaluated_on}, expected "
            f"{evaluated_at.date()}."
        )

    if (
        activation.status
        == ControlActivationStatus.ACTIVE
    ):
        if (
            tuple(activation.active_requirement_ids)
            != tuple(control.requirement_ids)
        ):
            raise ValueError(
                "ACTIVE Control activation must expose "
                "the complete ordered control requirement set."
            )

    elif activation.active_requirement_ids:
        raise ValueError(
            "Inactive Control activation cannot expose "
            "active_requirement_ids."
        )


def _validate_requirement_assessments(
    *,
    catalogue: PolicyCatalogue,
    activation: ControlActivationResult,
    requirement_assessments: tuple[
        RequirementAssessment,
        ...,
    ],
) -> dict[str, RequirementAssessment]:
    control = catalogue.controls[
        activation.control_id
    ]

    assessments_by_id: dict[
        str,
        RequirementAssessment,
    ] = {}

    expected_scope = (
        requirement_assessments[0].scope
        if requirement_assessments
        else None
    )

    for assessment in requirement_assessments:
        if (
            expected_scope is not None
            and assessment.scope != expected_scope
        ):
            raise ValueError(
                "RequirementAssessments for one control "
                "governance evaluation must share the "
                "same evidence scope."
            )

        if assessment.requirement_id in assessments_by_id:
            raise ValueError(
                "Duplicate RequirementAssessment for "
                f"requirement: {assessment.requirement_id}."
            )

        if (
            assessment.requirement_id
            not in catalogue.requirements
        ):
            raise ValueError(
                "RequirementAssessment references unknown "
                "requirement: "
                f"{assessment.requirement_id}."
            )

        if (
            assessment.requirement_id
            not in control.requirement_ids
        ):
            raise ValueError(
                "RequirementAssessment references a "
                "requirement outside the control: "
                f"{assessment.requirement_id}."
            )

        requirement = catalogue.requirements[
            assessment.requirement_id
        ]

        if (
            assessment.check_definition_id
            != requirement.check_definition_id
        ):
            raise ValueError(
                "RequirementAssessment check-definition "
                "identity does not match CheckRequirement: "
                f"{assessment.requirement_id}."
            )

        if assessment.obligation != requirement.obligation:
            raise ValueError(
                "RequirementAssessment obligation does not "
                "match CheckRequirement: "
                f"{assessment.requirement_id}."
            )

        assessments_by_id[
            assessment.requirement_id
        ] = assessment

    active_requirement_ids = set(
        activation.active_requirement_ids
    )

    assessment_ids = set(
        assessments_by_id
    )

    missing_assessment_ids = [
        requirement_id
        for requirement_id
        in activation.active_requirement_ids
        if requirement_id not in assessment_ids
    ]

    if missing_assessment_ids:
        raise ValueError(
            "Active requirements are missing factual "
            "RequirementAssessment objects: "
            f"{missing_assessment_ids}."
        )

    extra_assessment_ids = [
        requirement_id
        for requirement_id
        in assessments_by_id
        if requirement_id
        not in active_requirement_ids
    ]

    if extra_assessment_ids:
        raise ValueError(
            "RequirementAssessment supplied for inactive "
            "control requirements: "
            f"{extra_assessment_ids}."
        )

    return assessments_by_id


def _validate_exception_resolutions(
    *,
    catalogue: PolicyCatalogue,
    activation: ControlActivationResult,
    exception_resolutions: tuple[
        PolicyExceptionResolution,
        ...,
    ],
    evaluated_at: datetime,
) -> tuple[
    set[str],
    tuple[str, ...],
]:
    control = catalogue.controls[
        activation.control_id
    ]

    active_requirement_ids = set(
        activation.active_requirement_ids
    )

    effectively_excepted: set[str] = set()
    effective_exception_ids: list[str] = []
    seen_exception_ids: set[str] = set()

    for resolution in exception_resolutions:
        if resolution.exception_id in seen_exception_ids:
            raise ValueError(
                "Duplicate PolicyExceptionResolution for "
                "exception: "
                f"{resolution.exception_id}."
            )

        seen_exception_ids.add(
            resolution.exception_id
        )

        if resolution.policy_id != activation.policy_id:
            raise ValueError(
                "PolicyExceptionResolution policy identity "
                "does not match control activation: "
                f"{resolution.policy_id}, expected "
                f"{activation.policy_id}."
            )

        if resolution.control_id != activation.control_id:
            raise ValueError(
                "PolicyExceptionResolution control identity "
                "does not match control activation: "
                f"{resolution.control_id}, expected "
                f"{activation.control_id}."
            )

        if resolution.evaluated_at != evaluated_at:
            raise ValueError(
                "PolicyExceptionResolution evaluation "
                "instant does not match governance "
                "evaluation instant."
            )

        if (
            resolution.activation_status
            != activation.status
        ):
            raise ValueError(
                "PolicyExceptionResolution activation "
                "status does not match the supplied "
                "ControlActivationResult."
            )

        if (
            resolution.status
            == PolicyExceptionResolutionStatus.EFFECTIVE
        ):
            if (
                activation.status
                != ControlActivationStatus.ACTIVE
            ):
                raise ValueError(
                    "An effective PolicyExceptionResolution "
                    "cannot target an inactive control."
                )

            if not resolution.effective_requirement_ids:
                raise ValueError(
                    "Effective PolicyExceptionResolution "
                    "must expose at least one requirement."
                )

            invalid_requirement_ids = [
                requirement_id
                for requirement_id
                in resolution.effective_requirement_ids
                if (
                    requirement_id
                    not in active_requirement_ids
                    or requirement_id
                    not in control.requirement_ids
                )
            ]

            if invalid_requirement_ids:
                raise ValueError(
                    "Effective PolicyExceptionResolution "
                    "references requirements outside the "
                    "active control: "
                    f"{invalid_requirement_ids}."
                )

            effective_exception_ids.append(
                resolution.exception_id
            )

            effectively_excepted.update(
                resolution.effective_requirement_ids
            )

        elif resolution.effective_requirement_ids:
            raise ValueError(
                "Non-effective PolicyExceptionResolution "
                "cannot expose effective_requirement_ids."
            )

    return (
        effectively_excepted,
        tuple(effective_exception_ids),
    )


def _ordered_ids(
    *,
    control_requirement_ids: Iterable[str],
    selected_ids: set[str],
) -> tuple[str, ...]:
    return tuple(
        requirement_id
        for requirement_id in control_requirement_ids
        if requirement_id in selected_ids
    )


def _inactive_result(
    *,
    activation: ControlActivationResult,
    evaluated_at: datetime,
) -> ControlGovernanceAssessment:
    if (
        activation.status
        == ControlActivationStatus.NOT_APPLICABLE
    ):
        status = (
            ControlGovernanceStatus.NOT_APPLICABLE
        )

    elif (
        activation.status
        == ControlActivationStatus.INDETERMINATE
    ):
        status = (
            ControlGovernanceStatus.INDETERMINATE
        )

    elif activation.status in {
        ControlActivationStatus.NOT_YET_EFFECTIVE,
        ControlActivationStatus.EXPIRED,
    }:
        status = (
            ControlGovernanceStatus.NOT_IN_EFFECT
        )

    else:
        raise ValueError(
            "Unsupported inactive Control activation "
            f"status: {activation.status}."
        )

    return ControlGovernanceAssessment(
        policy_id=activation.policy_id,
        control_id=activation.control_id,
        evaluated_at=evaluated_at,
        activation_status=activation.status,
        status=status,
    )


def assess_control_governance(
    *,
    catalogue: PolicyCatalogue,
    activation: ControlActivationResult,
    requirement_assessments: Iterable[
        RequirementAssessment
    ],
    exception_resolutions: Iterable[
        PolicyExceptionResolution
    ] = (),
    evaluated_at: datetime,
) -> ControlGovernanceAssessment:
    """
    Interpret governance state for one PolicyControl.

    ACTIVE-control precedence:
      1. any unexcepted REQUIRED FAILED -> NON_COMPLIANT;
      2. otherwise any unexcepted REQUIRED
         MISSING/INSUFFICIENT -> INCOMPLETE;
      3. otherwise any excepted REQUIRED issue -> EXCEPTED;
      4. otherwise -> COMPLIANT.

    RECOMMENDED issues are advisory only.

    Exceptions suppress governance consequences for the
    covered requirement, but never rewrite its factual
    RequirementAssessment status.
    """

    _validate_evaluated_at(
        evaluated_at
    )

    _validate_activation(
        catalogue=catalogue,
        activation=activation,
        evaluated_at=evaluated_at,
    )

    assessments = tuple(
        requirement_assessments
    )

    resolutions = tuple(
        exception_resolutions
    )

    if (
        activation.status
        != ControlActivationStatus.ACTIVE
    ):
        if assessments:
            raise ValueError(
                "Inactive Control governance evaluation "
                "cannot consume RequirementAssessment "
                "objects."
            )

        if resolutions:
            _validate_exception_resolutions(
                catalogue=catalogue,
                activation=activation,
                exception_resolutions=resolutions,
                evaluated_at=evaluated_at,
            )

        return _inactive_result(
            activation=activation,
            evaluated_at=evaluated_at,
        )

    assessments_by_id = (
        _validate_requirement_assessments(
            catalogue=catalogue,
            activation=activation,
            requirement_assessments=assessments,
        )
    )

    (
        effectively_excepted,
        effective_exception_ids,
    ) = _validate_exception_resolutions(
        catalogue=catalogue,
        activation=activation,
        exception_resolutions=resolutions,
        evaluated_at=evaluated_at,
    )

    control = catalogue.controls[
        activation.control_id
    ]

    failed_ids: set[str] = set()
    missing_ids: set[str] = set()
    insufficient_ids: set[str] = set()

    excepted_issue_ids: set[str] = set()
    advisory_ids: set[str] = set()

    unexcepted_required_ids: set[str] = set()
    unexcepted_required_failed_ids: set[str] = set()
    unexcepted_required_incomplete_ids: set[str] = set()

    excepted_required_issue_ids: set[str] = set()

    for requirement_id in control.requirement_ids:
        assessment = assessments_by_id[
            requirement_id
        ]

        requirement = catalogue.requirements[
            requirement_id
        ]

        factual_issue = (
            assessment.status
            != RequirementAssessmentStatus.SATISFIED
        )

        if (
            assessment.status
            == RequirementAssessmentStatus.FAILED
        ):
            failed_ids.add(
                requirement_id
            )

        elif (
            assessment.status
            == RequirementAssessmentStatus.MISSING
        ):
            missing_ids.add(
                requirement_id
            )

        elif (
            assessment.status
            == RequirementAssessmentStatus.INSUFFICIENT
        ):
            insufficient_ids.add(
                requirement_id
            )

        if not factual_issue:
            continue

        if requirement_id in effectively_excepted:
            excepted_issue_ids.add(
                requirement_id
            )

            if (
                requirement.obligation
                == RequirementObligation.REQUIRED
            ):
                excepted_required_issue_ids.add(
                    requirement_id
                )

            continue

        if (
            requirement.obligation
            == RequirementObligation.RECOMMENDED
        ):
            advisory_ids.add(
                requirement_id
            )
            continue

        unexcepted_required_ids.add(
            requirement_id
        )

        if (
            assessment.status
            == RequirementAssessmentStatus.FAILED
        ):
            unexcepted_required_failed_ids.add(
                requirement_id
            )

        elif assessment.status in {
            RequirementAssessmentStatus.MISSING,
            RequirementAssessmentStatus.INSUFFICIENT,
        }:
            unexcepted_required_incomplete_ids.add(
                requirement_id
            )

    if unexcepted_required_failed_ids:
        status = (
            ControlGovernanceStatus.NON_COMPLIANT
        )

    elif unexcepted_required_incomplete_ids:
        status = (
            ControlGovernanceStatus.INCOMPLETE
        )

    elif excepted_required_issue_ids:
        status = (
            ControlGovernanceStatus.EXCEPTED
        )

    else:
        status = (
            ControlGovernanceStatus.COMPLIANT
        )

    return ControlGovernanceAssessment(
        policy_id=activation.policy_id,
        control_id=activation.control_id,
        evaluated_at=evaluated_at,
        activation_status=activation.status,
        status=status,
        failed_requirement_ids=_ordered_ids(
            control_requirement_ids=(
                control.requirement_ids
            ),
            selected_ids=failed_ids,
        ),
        missing_requirement_ids=_ordered_ids(
            control_requirement_ids=(
                control.requirement_ids
            ),
            selected_ids=missing_ids,
        ),
        insufficient_requirement_ids=_ordered_ids(
            control_requirement_ids=(
                control.requirement_ids
            ),
            selected_ids=insufficient_ids,
        ),
        excepted_requirement_ids=_ordered_ids(
            control_requirement_ids=(
                control.requirement_ids
            ),
            selected_ids=excepted_issue_ids,
        ),
        advisory_requirement_ids=_ordered_ids(
            control_requirement_ids=(
                control.requirement_ids
            ),
            selected_ids=advisory_ids,
        ),
        unexcepted_required_requirement_ids=(
            _ordered_ids(
                control_requirement_ids=(
                    control.requirement_ids
                ),
                selected_ids=(
                    unexcepted_required_ids
                ),
            )
        ),
        effective_exception_ids=(
            effective_exception_ids
        ),
    )
