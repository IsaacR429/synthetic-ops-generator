from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class LogSeverity(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class OperationalLog(BaseModel):
    log_id: str = Field(min_length=1)
    chg_id: str = Field(min_length=1)

    log_type: str = Field(min_length=1)
    severity: LogSeverity

    message: str = Field(min_length=1)

    service: str = Field(min_length=1)
    component: str | None = None

    timestamp: datetime

    error_code: str | None = None

    attributes: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("timestamp")
    @classmethod
    def validate_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Operational Log timestamp "
                "must be timezone-aware."
            )

        return value