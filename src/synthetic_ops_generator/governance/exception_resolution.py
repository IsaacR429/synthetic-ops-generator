from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from synthetic_ops_generator.governance.activation import (
    ControlActivationResult,
    ControlActivationStatus,
)
from synthetic_ops_generator.governance.exceptions import (
    PolicyException,
    PolicyExceptionScope,
    PolicyExceptionStatus,
)
from synthetic_ops_generator.governance.models import (
    PolicyCatalogue,
)


class PolicyExceptionResolutionStatus(StrEnum):
    """
    Effective state of one formal governance exception.

    Resolution combines:
      - validated catalogue references;
      - an existing P3C control-activation result;
      - P3D1 exception lifecycle facts;
      - one timezone-aware evaluation instant.

    It does not assess evidence, compliance, blocking,
    readiness, or runtime decisions.
    """

    EFFECTIVE = "effective"
    NOT_APPROVED = "not_approved"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"
    REVOKED = "revoked"
    TARGET_NOT_ACTIVE = "target_not_active"


class PolicyExceptionResolution(BaseModel):
    """
    Auditable resolution of one PolicyException.

    effective_requirement_ids are populated only when
    the exception is effective for an ACTIVE control.
    """

    model_config = ConfigDict(frozen=True)

    exception_id: str
    policy_id: str
    control_id: str

    evaluated_at: datetime

    exception_status: PolicyExceptionStatus
    activation_status: ControlActivationStatus

    status: PolicyExceptionResolutionStatus

    effective_requirement_ids: tuple[str, ...] = ()


def _validate_evaluated_at(
    evaluated_at: datetime,
) -> None:
    if (
        evaluated_at.tzinfo is None
        or evaluated_at.utcoffset() is None
    ):
        raise ValueError(
            "Policy Exception resolution requires a "
            "timezone-aware evaluated_at timestamp."
        )


def _validate_references(
    *,
    catalogue: PolicyCatalogue,
    activation: ControlActivationResult,
    exception: PolicyException,
    evaluated_at: datetime,
) -> None:
    policy = catalogue.policies.get(
        exception.policy_id
    )

    if policy is None:
        raise ValueError(
            "Policy Exception references unknown policy: "
            f"{exception.policy_id}."
        )

    control = catalogue.controls.get(
        exception.control_id
    )

    if control is None:
        raise ValueError(
            "Policy Exception references unknown control: "
            f"{exception.control_id}."
        )

    if control.policy_id != exception.policy_id:
        raise ValueError(
            "Policy Exception control does not belong to "
            "the referenced policy: "
            f"{exception.control_id} -> "
            f"{control.policy_id}, expected "
            f"{exception.policy_id}."
        )

    if activation.policy_id != exception.policy_id:
        raise ValueError(
            "Control activation policy identity does not "
            "match Policy Exception: "
            f"{activation.policy_id}, expected "
            f"{exception.policy_id}."
        )

    if activation.control_id != exception.control_id:
        raise ValueError(
            "Control activation identity does not match "
            "Policy Exception: "
            f"{activation.control_id}, expected "
            f"{exception.control_id}."
        )

    if activation.evaluated_on != evaluated_at.date():
        raise ValueError(
            "Control activation evaluation date does not "
            "match exception resolution date: "
            f"{activation.evaluated_on}, expected "
            f"{evaluated_at.date()}."
        )

    control_requirement_ids = set(
        control.requirement_ids
    )

    if (
        exception.scope
        == PolicyExceptionScope.REQUIREMENT
    ):
        unknown_requirement_ids = [
            requirement_id
            for requirement_id
            in exception.requirement_ids
            if requirement_id
            not in control_requirement_ids
        ]

        if unknown_requirement_ids:
            raise ValueError(
                "Policy Exception references requirements "
                "outside its control: "
                f"{unknown_requirement_ids}."
            )

        for requirement_id in exception.requirement_ids:
            if requirement_id not in catalogue.requirements:
                raise ValueError(
                    "Policy Exception references unknown "
                    "requirement: "
                    f"{requirement_id}."
                )

    elif (
        exception.scope
        == PolicyExceptionScope.CONTROL
        and exception.requirement_ids
    ):
        raise ValueError(
            "Control-scoped Policy Exception cannot "
            "declare requirement_ids."
        )

    if (
        activation.status
        != ControlActivationStatus.ACTIVE
        and activation.active_requirement_ids
    ):
        raise ValueError(
            "Inactive Control activation cannot expose "
            "active_requirement_ids."
        )

    if (
        activation.status
        == ControlActivationStatus.ACTIVE
    ):
        unknown_active_requirement_ids = [
            requirement_id
            for requirement_id
            in activation.active_requirement_ids
            if requirement_id
            not in control_requirement_ids
        ]

        if unknown_active_requirement_ids:
            raise ValueError(
                "Control activation exposes requirements "
                "outside its control: "
                f"{unknown_active_requirement_ids}."
            )

        if (
            tuple(activation.active_requirement_ids)
            != tuple(control.requirement_ids)
        ):
            raise ValueError(
                "ACTIVE Control activation must expose "
                "the complete ordered control requirement "
                "set."
            )


def _result(
    *,
    activation: ControlActivationResult,
    exception: PolicyException,
    evaluated_at: datetime,
    status: PolicyExceptionResolutionStatus,
    effective_requirement_ids: tuple[str, ...] = (),
) -> PolicyExceptionResolution:
    return PolicyExceptionResolution(
        exception_id=exception.exception_id,
        policy_id=exception.policy_id,
        control_id=exception.control_id,
        evaluated_at=evaluated_at,
        exception_status=exception.status,
        activation_status=activation.status,
        status=status,
        effective_requirement_ids=(
            effective_requirement_ids
        ),
    )


def resolve_policy_exception(
    *,
    catalogue: PolicyCatalogue,
    activation: ControlActivationResult,
    exception: PolicyException,
    evaluated_at: datetime,
) -> PolicyExceptionResolution:
    """
    Resolve whether a PolicyException is effective.

    Resolution precedence:
      1. structural/reference validation;
      2. REQUESTED / REJECTED -> NOT_APPROVED;
      3. before valid_from -> NOT_YET_EFFECTIVE;
      4. after valid_to -> EXPIRED;
      5. at/after revoked_on -> REVOKED;
      6. target control not ACTIVE -> TARGET_NOT_ACTIVE;
      7. otherwise -> EFFECTIVE.

    valid_from and valid_to boundaries are inclusive.
    Revocation is effective at revoked_on.

    A REVOKED record may therefore still resolve as
    EFFECTIVE for an evaluation instant before revoked_on.
    """

    _validate_evaluated_at(evaluated_at)

    _validate_references(
        catalogue=catalogue,
        activation=activation,
        exception=exception,
        evaluated_at=evaluated_at,
    )

    if exception.status in {
        PolicyExceptionStatus.REQUESTED,
        PolicyExceptionStatus.REJECTED,
    }:
        return _result(
            activation=activation,
            exception=exception,
            evaluated_at=evaluated_at,
            status=(
                PolicyExceptionResolutionStatus.NOT_APPROVED
            ),
        )

    if exception.status not in {
        PolicyExceptionStatus.APPROVED,
        PolicyExceptionStatus.REVOKED,
    }:
        raise ValueError(
            "Unsupported Policy Exception lifecycle "
            f"status: {exception.status}."
        )

    if (
        exception.valid_from is None
        or exception.valid_to is None
    ):
        raise ValueError(
            "Approved or revoked Policy Exception "
            "requires a complete validity window."
        )

    if evaluated_at < exception.valid_from:
        return _result(
            activation=activation,
            exception=exception,
            evaluated_at=evaluated_at,
            status=(
                PolicyExceptionResolutionStatus
                .NOT_YET_EFFECTIVE
            ),
        )

    if evaluated_at > exception.valid_to:
        return _result(
            activation=activation,
            exception=exception,
            evaluated_at=evaluated_at,
            status=(
                PolicyExceptionResolutionStatus.EXPIRED
            ),
        )

    if (
        exception.status
        == PolicyExceptionStatus.REVOKED
    ):
        if exception.revoked_on is None:
            raise ValueError(
                "Revoked Policy Exception requires "
                "revoked_on."
            )

        if evaluated_at >= exception.revoked_on:
            return _result(
                activation=activation,
                exception=exception,
                evaluated_at=evaluated_at,
                status=(
                    PolicyExceptionResolutionStatus
                    .REVOKED
                ),
            )

    if (
        activation.status
        != ControlActivationStatus.ACTIVE
    ):
        return _result(
            activation=activation,
            exception=exception,
            evaluated_at=evaluated_at,
            status=(
                PolicyExceptionResolutionStatus
                .TARGET_NOT_ACTIVE
            ),
        )

    if (
        exception.scope
        == PolicyExceptionScope.CONTROL
    ):
        effective_requirement_ids = (
            activation.active_requirement_ids
        )

    elif (
        exception.scope
        == PolicyExceptionScope.REQUIREMENT
    ):
        active_requirement_ids = set(
            activation.active_requirement_ids
        )

        inactive_targets = [
            requirement_id
            for requirement_id
            in exception.requirement_ids
            if requirement_id
            not in active_requirement_ids
        ]

        if inactive_targets:
            raise ValueError(
                "Policy Exception targets requirements "
                "not active for the control: "
                f"{inactive_targets}."
            )

        effective_requirement_ids = (
            exception.requirement_ids
        )

    else:
        raise ValueError(
            "Unsupported Policy Exception scope: "
            f"{exception.scope}."
        )

    return _result(
        activation=activation,
        exception=exception,
        evaluated_at=evaluated_at,
        status=(
            PolicyExceptionResolutionStatus.EFFECTIVE
        ),
        effective_requirement_ids=(
            effective_requirement_ids
        ),
    )
