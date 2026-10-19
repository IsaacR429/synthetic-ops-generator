from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from synthetic_ops_generator.domain.change import (
    Change,
    ChangeStatus,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    RiskLevel,
)
from synthetic_ops_generator.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from synthetic_ops_generator.temporal.incident_attribution import (
    IncidentTemporalRelationship,
    assess_incident_temporal_attribution,
)


def _dt(
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        6,
        10,
        hour,
        minute,
        tzinfo=timezone.utc,
    )


def _change() -> Change:
    return Change(
        chg_id="CHG-2026-001",
        business_stream="claims",
        service="claims-processing",
        components=["claims-api"],
        risk=RiskLevel.HIGH,
        owner="change.manager@example.test",
        environment=Environment.PRODUCTION,
        status=ChangeStatus.COMPLETED,
        implementation_window_start=_dt(10, 0),
        implementation_window_end=_dt(10, 30),
    )


def _incident(
    *,
    created_at: datetime,
    chg_id: str | None = "CHG-2026-001",
    service: str = "claims-processing",
) -> Incident:
    return Incident(
        incident_id="INC-2026-001",
        chg_id=chg_id,
        title="Service degradation",
        description="Observed operational degradation.",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        service=service,
        component="claims-api",
        created_at=created_at,
    )


WINDOW = timedelta(minutes=30)


def test_incident_before_implementation_is_not_candidate() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(9, 59),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.BEFORE_IMPLEMENTATION
    )

    assert result.is_temporal_candidate is False


def test_implementation_start_boundary_is_during_implementation() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 0),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.DURING_IMPLEMENTATION
    )

    assert result.is_temporal_candidate is True


def test_incident_during_implementation_is_candidate() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 15),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.DURING_IMPLEMENTATION
    )

    assert result.is_temporal_candidate is True


def test_implementation_end_boundary_starts_post_change_window() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 30),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is True


def test_incident_inside_post_change_window_is_candidate() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is True


def test_attribution_window_end_boundary_is_inclusive() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(11, 0),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is True


def test_incident_after_post_change_window_is_not_candidate() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(11, 1),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.AFTER_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is False


@pytest.mark.parametrize(
    "invalid_window",
    [
        timedelta(0),
        timedelta(seconds=-1),
    ],
)
def test_post_change_window_must_be_positive(
    invalid_window: timedelta,
) -> None:
    with pytest.raises(ValueError):
        assess_incident_temporal_attribution(
            change=_change(),
            incident=_incident(
                created_at=_dt(10, 45),
            ),
            post_change_window=invalid_window,
        )


def test_temporal_attribution_does_not_require_incident_chg_id() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
            chg_id=None,
        ),
        post_change_window=WINDOW,
    )

    assert result.is_temporal_candidate is True


def test_declared_change_id_mismatch_does_not_rewrite_time_fact() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
            chg_id="CHG-OTHER",
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is True


def test_service_mismatch_does_not_rewrite_time_fact() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
            service="claims-payment",
        ),
        post_change_window=WINDOW,
    )

    assert result.is_temporal_candidate is True


def test_result_preserves_temporal_audit_facts() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
        ),
        post_change_window=WINDOW,
    )

    assert result.chg_id == "CHG-2026-001"
    assert result.incident_id == "INC-2026-001"

    assert (
        result.implementation_window_start
        == _dt(10, 0)
    )

    assert (
        result.implementation_window_end
        == _dt(10, 30)
    )

    assert (
        result.post_change_window_end
        == _dt(11, 0)
    )

    assert result.incident_created_at == _dt(10, 45)


def test_result_is_frozen() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
        ),
        post_change_window=WINDOW,
    )

    with pytest.raises(Exception):
        result.is_temporal_candidate = False


def test_result_does_not_claim_causality() -> None:
    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=_incident(
            created_at=_dt(10, 45),
        ),
        post_change_window=WINDOW,
    )

    fields = result.model_fields

    assert "caused_by_change" not in fields
    assert "root_cause" not in fields
    assert "probable_cause" not in fields
    assert "confidence" not in fields
    assert "decision" not in fields
    assert "action" not in fields

@pytest.mark.parametrize(
    "implementation_end",
    [
        _dt(10, 0),
        _dt(9, 59),
    ],
)
def test_forged_invalid_change_window_is_rejected(
    implementation_end: datetime,
) -> None:
    change = _change().model_copy(
        update={
            "implementation_window_end": (
                implementation_end
            ),
        }
    )

    with pytest.raises(ValueError):
        assess_incident_temporal_attribution(
            change=change,
            incident=_incident(
                created_at=_dt(10, 15),
            ),
            post_change_window=WINDOW,
        )


def test_forged_naive_incident_timestamp_is_rejected() -> None:
    incident = _incident(
        created_at=_dt(10, 45),
    ).model_copy(
        update={
            "created_at": datetime(
                2026,
                6,
                10,
                10,
                45,
            ),
        }
    )

    with pytest.raises(ValueError):
        assess_incident_temporal_attribution(
            change=_change(),
            incident=incident,
            post_change_window=WINDOW,
        )


def test_equivalent_instant_with_different_offset_is_compared_correctly() -> None:
    offset = timezone(
        timedelta(hours=2)
    )

    incident = _incident(
        created_at=datetime(
            2026,
            6,
            10,
            12,
            45,
            tzinfo=offset,
        ),
    )

    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=incident,
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is True


def test_resolved_at_does_not_change_incident_onset_relationship() -> None:
    incident = Incident(
        incident_id="INC-2026-001",
        chg_id="CHG-2026-001",
        title="Service degradation",
        description="Observed operational degradation.",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RESOLVED,
        service="claims-processing",
        component="claims-api",
        created_at=_dt(10, 45),
        resolved_at=_dt(11, 30),
    )

    result = assess_incident_temporal_attribution(
        change=_change(),
        incident=incident,
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.incident_created_at == _dt(10, 45)


def test_change_status_does_not_rewrite_temporal_relationship() -> None:
    change = _change().model_copy(
        update={
            "status": ChangeStatus.FAILED,
        }
    )

    result = assess_incident_temporal_attribution(
        change=change,
        incident=_incident(
            created_at=_dt(10, 45),
        ),
        post_change_window=WINDOW,
    )

    assert (
        result.relationship
        == IncidentTemporalRelationship.WITHIN_POST_CHANGE_WINDOW
    )

    assert result.is_temporal_candidate is True
