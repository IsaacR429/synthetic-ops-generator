from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)


class GeneratedEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    schema_version: str = "1.0"

    event_time: datetime

    source_system: str = Field(min_length=1)
    source_domain: SourceDomain | None = None

    scenario_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)

    chg_id: str | None = None

    business_stream: str | None = None
    service: str | None = None
    component: str | None = None
    environment: Environment | None = None

    sequence_number: int = Field(ge=1)

    synthetic: bool = True

    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("event_time")
    @classmethod
    def validate_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("event_time must be timezone-aware")

        return value