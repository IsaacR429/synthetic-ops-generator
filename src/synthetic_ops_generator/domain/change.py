from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from synthetic_ops_generator.domain.enums import Environment, RiskLevel


class ChangeStatus(StrEnum):
    CREATED = "created"
    APPROVED = "approved"
    IMPLEMENTING = "implementing"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    REQUEST = "request"
    APPROVED = "approved"
    REJECTED = "rejected"
    MISSING = "missing"
    WAIVED = "waived"


class Approval(BaseModel):
    approval_id: str = Field(min_length=1)
    chg_id: str = Field(min_length=1)

    approval_type: str = Field(min_length=1)
    status: ApprovalStatus
    source: str = Field(min_length=1)

    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Approval timestamp must be timezone-aware."
            )

        return value


class Change(BaseModel):
    chg_id: str = Field(min_length=1)

    business_stream: str = Field(min_length=1)
    service: str = Field(min_length=1)

    components: list[str] = Field(
        default_factory=list
    )

    risk: RiskLevel
    owner: str = Field(min_length=1)
    environment: Environment

    status: ChangeStatus

    implementation_window_start: datetime
    implementation_window_end: datetime

    approvals: list[Approval] = Field(
        default_factory=list
    )

    @field_validator(
        "implementation_window_start",
        "implementation_window_end",
    )
    @classmethod
    def validate_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Implementation-window timestamps "
                "must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_change(self) -> "Change":
        if (
            self.implementation_window_end
            <= self.implementation_window_start
        ):
            raise ValueError(
                "Implementation window end must occur "
                "after implementation window start."
            )

        for approval in self.approvals:
            if approval.chg_id != self.chg_id:
                raise ValueError(
                    "Approval CHG ID must match Change CHG ID."
                )

        return self
