from datetime import datetime
from enum import StrEnum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class PolicyExceptionType(StrEnum):
    """
    Type of formal governance exception.

    P3D1 introduces only the waiver type required by the current
    governance lifecycle. Additional exception types should be added
    only when their semantics are explicitly defined.
    """

    WAIVER = "waiver"


class PolicyExceptionStatus(StrEnum):
    """
    Lifecycle state of a formal governance exception request.
    """

    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


class PolicyExceptionScope(StrEnum):
    """
    Governance scope affected by the exception.

    CONTROL applies to the complete control.

    REQUIREMENT applies only to explicitly identified requirements
    belonging to that control.
    """

    CONTROL = "control"
    REQUIREMENT = "requirement"


class PolicyException(BaseModel):
    """
    Immutable governance record representing a formal policy exception.

    This model owns exception lifecycle facts only.

    It does not determine whether the referenced policy, control, or
    requirements currently exist or are active, and it does not alter
    compliance, blocking, or runtime decisions.
    """

    model_config = ConfigDict(frozen=True)

    exception_id: str = Field(min_length=1)

    exception_type: PolicyExceptionType
    status: PolicyExceptionStatus

    policy_id: str = Field(min_length=1)
    control_id: str = Field(min_length=1)

    scope: PolicyExceptionScope

    requirement_ids: tuple[str, ...] = ()

    reason: str = Field(min_length=1)

    requested_by: str = Field(min_length=1)
    requested_on: datetime

    decided_by: str | None = Field(
        default=None,
        min_length=1,
    )
    decided_on: datetime | None = None
    decision_reference: str | None = Field(
        default=None,
        min_length=1,
    )

    valid_from: datetime | None = None
    valid_to: datetime | None = None

    revoked_by: str | None = Field(
        default=None,
        min_length=1,
    )
    revoked_on: datetime | None = None
    revocation_reason: str | None = Field(
        default=None,
        min_length=1,
    )

    source_reference: str | None = Field(
        default=None,
        min_length=1,
    )

    @field_validator(
        "requested_on",
        "decided_on",
        "valid_from",
        "valid_to",
        "revoked_on",
    )
    @classmethod
    def validate_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Policy Exception timestamps must be "
                "timezone-aware."
            )

        return value

    @field_validator("requirement_ids")
    @classmethod
    def validate_requirement_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(
            not requirement_id.strip()
            for requirement_id in value
        ):
            raise ValueError(
                "Policy Exception requirement references "
                "cannot be empty."
            )

        if len(value) != len(set(value)):
            raise ValueError(
                "Policy Exception requirement references "
                "cannot contain duplicates."
            )

        return value

    @model_validator(mode="after")
    def validate_exception(
        self,
    ) -> "PolicyException":
        if (
            self.scope == PolicyExceptionScope.CONTROL
            and self.requirement_ids
        ):
            raise ValueError(
                "Control-scoped Policy Exception cannot "
                "declare requirement_ids."
            )

        if (
            self.scope == PolicyExceptionScope.REQUIREMENT
            and not self.requirement_ids
        ):
            raise ValueError(
                "Requirement-scoped Policy Exception "
                "requires at least one requirement_id."
            )

        decision_values = (
            self.decided_by,
            self.decided_on,
            self.decision_reference,
        )

        validity_values = (
            self.valid_from,
            self.valid_to,
        )

        revocation_values = (
            self.revoked_by,
            self.revoked_on,
            self.revocation_reason,
        )

        has_any_decision = any(
            value is not None
            for value in decision_values
        )
        has_complete_decision = all(
            value is not None
            for value in decision_values
        )

        has_any_validity = any(
            value is not None
            for value in validity_values
        )
        has_complete_validity = all(
            value is not None
            for value in validity_values
        )

        has_any_revocation = any(
            value is not None
            for value in revocation_values
        )
        has_complete_revocation = all(
            value is not None
            for value in revocation_values
        )

        if (
            self.decided_on is not None
            and self.decided_on < self.requested_on
        ):
            raise ValueError(
                "Policy Exception decision cannot precede "
                "the request."
            )

        if (
            self.decided_on is not None
            and self.valid_from is not None
            and self.valid_from < self.decided_on
        ):
            raise ValueError(
                "Policy Exception validity cannot begin "
                "before the decision."
            )

        if has_complete_validity:
            assert self.valid_from is not None
            assert self.valid_to is not None

            if self.valid_to <= self.valid_from:
                raise ValueError(
                    "Policy Exception valid_to must occur "
                    "after valid_from."
                )

        if (
            self.revoked_on is not None
            and self.decided_on is not None
            and self.revoked_on < self.decided_on
        ):
            raise ValueError(
                "Policy Exception revocation cannot precede "
                "the approval decision."
            )

        if self.status == PolicyExceptionStatus.REQUESTED:
            if has_any_decision:
                raise ValueError(
                    "Requested Policy Exception cannot contain "
                    "decision metadata."
                )

            if has_any_validity:
                raise ValueError(
                    "Requested Policy Exception cannot contain "
                    "an effective validity window."
                )

            if has_any_revocation:
                raise ValueError(
                    "Requested Policy Exception cannot contain "
                    "revocation metadata."
                )

            return self

        if self.status == PolicyExceptionStatus.APPROVED:
            if not has_complete_decision:
                raise ValueError(
                    "Approved Policy Exception requires complete "
                    "decision metadata."
                )

            if not has_complete_validity:
                raise ValueError(
                    "Approved Policy Exception requires a finite "
                    "validity window."
                )

            if has_any_revocation:
                raise ValueError(
                    "Approved Policy Exception cannot contain "
                    "revocation metadata."
                )

            return self

        if self.status == PolicyExceptionStatus.REJECTED:
            if not has_complete_decision:
                raise ValueError(
                    "Rejected Policy Exception requires complete "
                    "decision metadata."
                )

            if has_any_validity:
                raise ValueError(
                    "Rejected Policy Exception cannot contain "
                    "an effective validity window."
                )

            if has_any_revocation:
                raise ValueError(
                    "Rejected Policy Exception cannot contain "
                    "revocation metadata."
                )

            return self

        if self.status == PolicyExceptionStatus.REVOKED:
            if not has_complete_decision:
                raise ValueError(
                    "Revoked Policy Exception must preserve "
                    "complete approval decision metadata."
                )

            if not has_complete_validity:
                raise ValueError(
                    "Revoked Policy Exception must preserve "
                    "its approved finite validity window."
                )

            if not has_complete_revocation:
                raise ValueError(
                    "Revoked Policy Exception requires complete "
                    "revocation metadata."
                )

            return self

        raise ValueError(
            "Unsupported Policy Exception status: "
            f"{self.status}"
        )
