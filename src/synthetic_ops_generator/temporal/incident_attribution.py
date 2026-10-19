from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from synthetic_ops_generator.domain.change import Change
from synthetic_ops_generator.domain.incident import Incident


class IncidentTemporalRelationship(StrEnum):
    """
    Temporal position of an Incident relative to a Change.

    These states describe time only. They do not establish
    causal attribution between the Change and Incident.
    """

    BEFORE_IMPLEMENTATION = "before_implementation"
    DURING_IMPLEMENTATION = "during_implementation"
    WITHIN_POST_CHANGE_WINDOW = (
        "within_post_change_window"
    )
    AFTER_POST_CHANGE_WINDOW = (
        "after_post_change_window"
    )


class IncidentTemporalAttribution(BaseModel):
    """
    Auditable temporal relationship between one Change
    and one Incident.

    is_temporal_candidate means only that the Incident
    occurred during implementation or within the configured
    post-change attribution window.

    It does not mean that the Change caused the Incident.
    """

    model_config = ConfigDict(frozen=True)

    chg_id: str
    incident_id: str

    implementation_window_start: datetime
    implementation_window_end: datetime
    post_change_window_end: datetime

    incident_created_at: datetime

    relationship: IncidentTemporalRelationship
    is_temporal_candidate: bool


def _validate_post_change_window(
    post_change_window: timedelta,
) -> None:
    if post_change_window <= timedelta(0):
        raise ValueError(
            "Post-change attribution window must be "
            "greater than zero."
        )


def _validate_temporal_inputs(
    *,
    change: Change,
    incident: Incident,
) -> None:
    timestamps = (
        change.implementation_window_start,
        change.implementation_window_end,
        incident.created_at,
    )

    if any(
        timestamp.tzinfo is None
        or timestamp.utcoffset() is None
        for timestamp in timestamps
    ):
        raise ValueError(
            "Incident temporal attribution requires "
            "timezone-aware timestamps."
        )

    if (
        change.implementation_window_end
        <= change.implementation_window_start
    ):
        raise ValueError(
            "Change implementation window end must occur "
            "after implementation window start."
        )


def assess_incident_temporal_attribution(
    *,
    change: Change,
    incident: Incident,
    post_change_window: timedelta,
) -> IncidentTemporalAttribution:
    """
    Assess time-only Incident/Change association.

    Boundary semantics:

        implementation:
            [implementation_start, implementation_end)

        post-change:
            [implementation_end, post_change_window_end]

    Therefore an Incident exactly at implementation_end
    belongs to the post-change window, and an Incident
    exactly at post_change_window_end remains inside it.

    Incident.chg_id, service identity, topology, RCA,
    confidence, and causal interpretation are deliberately
    excluded from this calculation.
    """

    _validate_post_change_window(
        post_change_window
    )

    _validate_temporal_inputs(
        change=change,
        incident=incident,
    )

    implementation_start = (
        change.implementation_window_start
    )
    implementation_end = (
        change.implementation_window_end
    )

    post_change_window_end = (
        implementation_end
        + post_change_window
    )

    incident_created_at = incident.created_at

    if incident_created_at < implementation_start:
        relationship = (
            IncidentTemporalRelationship
            .BEFORE_IMPLEMENTATION
        )
        is_temporal_candidate = False

    elif incident_created_at < implementation_end:
        relationship = (
            IncidentTemporalRelationship
            .DURING_IMPLEMENTATION
        )
        is_temporal_candidate = True

    elif (
        incident_created_at
        <= post_change_window_end
    ):
        relationship = (
            IncidentTemporalRelationship
            .WITHIN_POST_CHANGE_WINDOW
        )
        is_temporal_candidate = True

    else:
        relationship = (
            IncidentTemporalRelationship
            .AFTER_POST_CHANGE_WINDOW
        )
        is_temporal_candidate = False

    return IncidentTemporalAttribution(
        chg_id=change.chg_id,
        incident_id=incident.incident_id,
        implementation_window_start=(
            implementation_start
        ),
        implementation_window_end=(
            implementation_end
        ),
        post_change_window_end=(
            post_change_window_end
        ),
        incident_created_at=incident_created_at,
        relationship=relationship,
        is_temporal_candidate=(
            is_temporal_candidate
        ),
    )
