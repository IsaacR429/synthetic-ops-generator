from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)


def created_at() -> datetime:
    return datetime(
        2026,
        8,
        13,
        10,
        0,
        tzinfo=UTC,
    )


def build_open_incident() -> Incident:
    return Incident(
        incident_id="INC0000001",
        chg_id="CHG0000001",
        title="Payment API degradation",
        description="Elevated failures detected.",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.OPEN,
        service="payment_service",
        component="payment_api",
        created_at=created_at(),
    )


def test_open_incident_accepts_valid_data() -> None:
    incident = build_open_incident()

    assert incident.incident_id == "INC0000001"
    assert incident.chg_id == "CHG0000001"
    assert incident.severity == IncidentSeverity.HIGH
    assert incident.status == IncidentStatus.OPEN


def test_incident_supports_component_scope() -> None:
    incident = build_open_incident()

    assert incident.service == "payment_service"
    assert incident.component == "payment_api"


def test_incident_allows_service_level_scope() -> None:
    incident = Incident(
        incident_id="INC0000001",
        title="Service degradation",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.OPEN,
        service="payment_service",
        component=None,
        created_at=created_at(),
    )

    assert incident.component is None


def test_incident_allows_no_change_link() -> None:
    incident = Incident(
        incident_id="INC0000001",
        chg_id=None,
        title="Unrelated infrastructure incident",
        severity=IncidentSeverity.MEDIUM,
        status=IncidentStatus.OPEN,
        service="payment_service",
        created_at=created_at(),
    )

    assert incident.chg_id is None


def test_resolved_incident_requires_resolution_time() -> None:
    with pytest.raises(
        ValidationError,
        match="requires resolved_at",
    ):
        Incident(
            incident_id="INC0000001",
            chg_id="CHG0000001",
            title="Payment API degradation",
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.RESOLVED,
            service="payment_service",
            created_at=created_at(),
        )


def test_resolved_incident_accepts_valid_lifecycle() -> None:
    incident = Incident(
        incident_id="INC0000001",
        chg_id="CHG0000001",
        title="Payment API degradation",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.RESOLVED,
        service="payment_service",
        component="payment_api",
        created_at=created_at(),
        resolved_at=created_at() + timedelta(minutes=15),
    )

    assert incident.status == IncidentStatus.RESOLVED
    assert incident.resolved_at is not None


def test_resolution_cannot_precede_creation() -> None:
    with pytest.raises(
        ValidationError,
        match="cannot precede created_at",
    ):
        Incident(
            incident_id="INC0000001",
            chg_id="CHG0000001",
            title="Payment API degradation",
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.RESOLVED,
            service="payment_service",
            created_at=created_at(),
            resolved_at=created_at() - timedelta(minutes=1),
        )


def test_open_incident_cannot_have_resolution_time() -> None:
    with pytest.raises(
        ValidationError,
        match="Unresolved Incident cannot have resolved_at",
    ):
        Incident(
            incident_id="INC0000001",
            chg_id="CHG0000001",
            title="Payment API degradation",
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            service="payment_service",
            created_at=created_at(),
            resolved_at=created_at() + timedelta(minutes=5),
        )


def test_incident_rejects_naive_creation_timestamp() -> None:
    naive_time = created_at().replace(
        tzinfo=None
    )

    with pytest.raises(
        ValidationError,
        match="timezone-aware",
    ):
        Incident(
            incident_id="INC0000001",
            title="Payment API degradation",
            severity=IncidentSeverity.HIGH,
            status=IncidentStatus.OPEN,
            service="payment_service",
            created_at=naive_time,
        )


def test_investigating_incident_is_supported() -> None:
    incident = Incident(
        incident_id="INC0000001",
        chg_id="CHG0000001",
        title="Payment API degradation",
        severity=IncidentSeverity.HIGH,
        status=IncidentStatus.INVESTIGATING,
        service="payment_service",
        component="payment_api",
        created_at=created_at(),
    )

    assert incident.status == IncidentStatus.INVESTIGATING