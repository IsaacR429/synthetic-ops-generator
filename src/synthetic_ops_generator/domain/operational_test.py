from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class TestCategory(StrEnum):
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"


class TestExecutionStatus(StrEnum):
    PLANNED = "planned"
    EXECUTED = "executed"


class TestResult(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class OperationalTest(BaseModel):
    test_id: str = Field(min_length=1)
    chg_id: str = Field(min_length=1)

    category: TestCategory

    test_type: str = Field(min_length=1)
    name: str = Field(min_length=1)

    service: str = Field(min_length=1)
    component: str | None = None

    mandatory: bool = True

    status: TestExecutionStatus
    result: TestResult | None = None

    planned_at: datetime
    executed_at: datetime | None = None

    failure_reason: str | None = None

    @field_validator(
        "planned_at",
        "executed_at",
    )
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "Operational Test timestamps "
                "must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_test(self) -> "OperationalTest":
        if self.status == TestExecutionStatus.PLANNED:
            if self.executed_at is not None:
                raise ValueError(
                    "Planned Test cannot have an execution time."
                )

            if self.result is not None:
                raise ValueError(
                    "Planned Test cannot have a result."
                )

        if self.status == TestExecutionStatus.EXECUTED:
            if self.executed_at is None:
                raise ValueError(
                    "Executed Test requires an execution time."
                )

            if self.result is None:
                raise ValueError(
                    "Executed Test requires a result."
                )

        if (
            self.executed_at is not None
            and self.executed_at < self.planned_at
        ):
            raise ValueError(
                "Test execution cannot occur before planning."
            )

        return self