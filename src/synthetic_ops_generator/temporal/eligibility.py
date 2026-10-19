from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from synthetic_ops_generator.domain.evidence import Evidence
from synthetic_ops_generator.domain.operational_test import (
    OperationalTest,
)


class TemporalEligibilityStatus(StrEnum):
    """
    Temporal position of an observation relative to a
    declared operational window.

    These states describe time eligibility only.
    """

    BEFORE_WINDOW = "before_window"
    WITHIN_WINDOW = "within_window"
    AFTER_WINDOW = "after_window"
    UNAVAILABLE = "unavailable"


class TemporalWindow(BaseModel):
    """
    Inclusive operational window.

    A TemporalWindow defines when an observation may be
    considered temporally eligible. It does not determine
    evidence quality, requirement satisfaction, governance
    compliance, or runtime decisions.
    """

    model_config = ConfigDict(frozen=True)

    window_id: str = Field(min_length=1)
    start_at: datetime
    end_at: datetime

    @field_validator(
        "start_at",
        "end_at",
    )
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "TemporalWindow timestamps must be "
                "timezone-aware."
            )

        return value

    @model_validator(mode="after")
    def validate_window(
        self,
    ) -> "TemporalWindow":
        if self.end_at <= self.start_at:
            raise ValueError(
                "TemporalWindow end_at must occur "
                "after start_at."
            )

        return self


class TemporalEligibilityResult(BaseModel):
    """
    Auditable time-only eligibility result.

    is_eligible means only that observed_at falls inside
    the supplied TemporalWindow.
    """

    model_config = ConfigDict(frozen=True)

    window_id: str
    window_start_at: datetime
    window_end_at: datetime

    observed_at: datetime | None

    status: TemporalEligibilityStatus
    is_eligible: bool


def _validate_window_integrity(
    window: TemporalWindow,
) -> None:
    timestamps = (
        window.start_at,
        window.end_at,
    )

    if any(
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
        for timestamp in timestamps
    ):
        raise ValueError(
            "Temporal eligibility requires timezone-aware "
            "window timestamps."
        )

    if window.end_at <= window.start_at:
        raise ValueError(
            "TemporalWindow end_at must occur "
            "after start_at."
        )


def _validate_observed_at(
    observed_at: datetime | None,
) -> None:
    if observed_at is None:
        return

    if (
        observed_at.tzinfo is None
        or observed_at.utcoffset() is None
    ):
        raise ValueError(
            "Temporal eligibility observed_at must be "
            "timezone-aware."
        )


def assess_temporal_eligibility(
    *,
    observed_at: datetime | None,
    window: TemporalWindow,
) -> TemporalEligibilityResult:
    """
    Assess whether one factual observation falls inside
    an inclusive TemporalWindow.

    Boundary semantics:

        [window.start_at, window.end_at]

    Missing observation time produces UNAVAILABLE rather
    than BEFORE/AFTER or an evidence-quality conclusion.
    """

    _validate_window_integrity(
        window
    )

    _validate_observed_at(
        observed_at
    )

    if observed_at is None:
        status = (
            TemporalEligibilityStatus.UNAVAILABLE
        )
        is_eligible = False

    elif observed_at < window.start_at:
        status = (
            TemporalEligibilityStatus.BEFORE_WINDOW
        )
        is_eligible = False

    elif observed_at <= window.end_at:
        status = (
            TemporalEligibilityStatus.WITHIN_WINDOW
        )
        is_eligible = True

    else:
        status = (
            TemporalEligibilityStatus.AFTER_WINDOW
        )
        is_eligible = False

    return TemporalEligibilityResult(
        window_id=window.window_id,
        window_start_at=window.start_at,
        window_end_at=window.end_at,
        observed_at=observed_at,
        status=status,
        is_eligible=is_eligible,
    )


def assess_evidence_temporal_eligibility(
    *,
    evidence: Evidence,
    window: TemporalWindow,
) -> TemporalEligibilityResult:
    """
    Assess Evidence using its factual captured_at time.

    evidence_type labels such as post_change_observation
    do not establish temporal eligibility.
    """

    return assess_temporal_eligibility(
        observed_at=evidence.captured_at,
        window=window,
    )

def assess_operational_test_temporal_eligibility(
    *,
    operational_test: OperationalTest,
    window: TemporalWindow,
) -> TemporalEligibilityResult:
    """
    Assess an OperationalTest using its factual execution
    timestamp.

    executed_at is the temporal observation used for an
    executed test. planned_at is deliberately not used as
    a substitute when execution has not occurred.

    PASSED / FAILED remains factual test truth and does not
    alter temporal eligibility.
    """

    return assess_temporal_eligibility(
        observed_at=operational_test.executed_at,
        window=window,
    )

