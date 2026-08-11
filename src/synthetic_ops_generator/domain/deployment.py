from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class DeploymentStatus(StrEnum):
    CREATED = "created"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"
    ROLLED_BACK = "rolled_back"
    REMEDIATION = "remediation"
    REMEDIATED = "remediated"


class DeploymentOutcome(StrEnum):
    SUCCESSFUL = "successful"
    DEGRADED = "degraded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    REMEDIATED = "remediated"


class Deployment(BaseModel):
    deployment_id: str = Field(min_length=1)
    chg_id: str = Field(min_length=1)

    artifact: str = Field(min_length=1)
    artifact_version: str = Field(min_length=1)

    service: str = Field(min_length=1)
    component: str | None = None

    start_time: datetime | None = None
    completion_time: datetime | None = None

    status: DeploymentStatus
    outcome: DeploymentOutcome | None = None

    @field_validator(
        "start_time",
        "completion_time",
    )
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "Deployment timestamps must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_deployment(self) -> "Deployment":
        if (
            self.completion_time is not None
            and self.start_time is None
        ):
            raise ValueError(
                "Deployment completion requires a start time."
            )

        if (
            self.start_time is not None
            and self.completion_time is not None
            and self.completion_time <= self.start_time
        ):
            raise ValueError(
                "Deployment completion must occur "
                "after deployment start."
            )

        if (
            self.status == DeploymentStatus.COMPLETED
            and self.outcome is None
        ):
            raise ValueError(
                "Completed Deployment requires an outcome."
            )

        return self
