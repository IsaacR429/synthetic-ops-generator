from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class Evidence(BaseModel):
    evidence_id: str = Field(min_length=1)
    chg_id: str = Field(min_length=1)

    evidence_type: str = Field(min_length=1)
    title: str = Field(min_length=1)

    service: str = Field(min_length=1)
    component: str | None = None

    captured_at: datetime

    source_event_ids: list[str] = Field(
        default_factory=list
    )
    source_record_ids: list[str] = Field(
        default_factory=list
    )

    attributes: dict[str, Any] = Field(
        default_factory=dict
    )

    @field_validator("captured_at")
    @classmethod
    def validate_timezone(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "Evidence captured_at must be timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_source_references(self) -> "Evidence":
        if (
            not self.source_event_ids
            and not self.source_record_ids
        ):
            raise ValueError(
                "Evidence must reference at least one "
                "source event or source record."
            )

        all_references = (
            self.source_event_ids
            + self.source_record_ids
        )

        if any(
            not reference.strip()
            for reference in all_references
        ):
            raise ValueError(
                "Evidence source references cannot be empty."
            )

        if (
            len(self.source_event_ids)
            != len(set(self.source_event_ids))
        ):
            raise ValueError(
                "Evidence source_event_ids "
                "cannot contain duplicates."
            )

        if (
            len(self.source_record_ids)
            != len(set(self.source_record_ids))
        ):
            raise ValueError(
                "Evidence source_record_ids "
                "cannot contain duplicates."
            )

        return self