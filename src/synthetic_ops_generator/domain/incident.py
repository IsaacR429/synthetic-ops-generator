from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(StrEnum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"


class Incident(BaseModel):
    incident_id: str = Field(min_length=1)

    chg_id: str | None = None

    title: str = Field(min_length=1)
    description: str | None = None

    severity: IncidentSeverity
    status: IncidentStatus

    service: str = Field(min_length=1)
    component: str | None = None

    created_at: datetime
    resolved_at: datetime | None = None

    @field_validator(
        "created_at",
        "resolved_at",
    )
    @classmethod
    def validate_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError(
                "Incident timestamps must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_lifecycle(self) -> "Incident":
        if self.status == IncidentStatus.RESOLVED:
            if self.resolved_at is None:
                raise ValueError(
                    "Resolved Incident requires resolved_at."
                )

            if self.resolved_at < self.created_at:
                raise ValueError(
                    "Incident resolved_at cannot precede created_at."
                )

            return self

        if self.resolved_at is not None:
            raise ValueError(
                "Unresolved Incident cannot have resolved_at."
            )

        return self