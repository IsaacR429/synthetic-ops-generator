from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class ManualValidationStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class ManualValidationResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    WAIVED = "waived"


class ManualValidation(BaseModel):
    validation_id: str = Field(min_length=1)
    chg_id: str = Field(min_length=1)

    validation_type: str = Field(min_length=1)
    name: str = Field(min_length=1)

    service: str = Field(min_length=1)
    component: str | None = None

    mandatory: bool = True

    status: ManualValidationStatus
    result: ManualValidationResult | None = None

    requested_at: datetime
    completed_at: datetime | None = None

    validated_by: str | None = None
    evidence_reference: str | None = None
    waiver_reason: str | None = None
    notes: str | None = None

    @field_validator(
        "requested_at",
        "completed_at",
    )
    @classmethod
    def validate_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "Manual Validation timestamps "
                "must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "ManualValidation":
        if self.status == ManualValidationStatus.PENDING:
            if self.result is not None:
                raise ValueError(
                    "Pending Manual Validation "
                    "cannot have a result."
                )

            if self.completed_at is not None:
                raise ValueError(
                    "Pending Manual Validation "
                    "cannot have completed_at."
                )

            return self

        if self.completed_at is None:
            raise ValueError(
                "Completed Manual Validation "
                "requires completed_at."
            )

        if self.result is None:
            raise ValueError(
                "Completed Manual Validation "
                "requires a result."
            )

        if self.completed_at < self.requested_at:
            raise ValueError(
                "Manual Validation completed_at "
                "cannot precede requested_at."
            )

        if (
            self.result == ManualValidationResult.WAIVED
            and not self.waiver_reason
        ):
            raise ValueError(
                "Waived Manual Validation "
                "requires a waiver reason."
            )

        return self