import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.domain.incident import (
    IncidentSeverity,
)
from synthetic_ops_generator.generators.incident import (
    IncidentDefinition,
    IncidentGenerator,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def build_context(
    *,
    state: OperationalState = OperationalState.OBSERVING,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-INC-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str = "incident_created",
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.INCIDENT,
        during_state=OperationalState.OBSERVING,
        profile_id=profile_id,
    )


async def collect_events(
    generator: IncidentGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_incident_created_profile_generates_one_event() -> None:
    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 1
    assert events[0].event_type == "itsm.incident.created"
    assert events[0].source_system == "synthetic_itsm"


def test_incident_resolved_profile_resolves_existing_incident() -> None:
    context = build_context()
    ids = IdFactory()

    create_generator = IncidentGenerator(
        ids=ids,
        behaviour=build_behaviour(),
    )

    created_events = asyncio.run(
        collect_events(
            create_generator,
            context,
        )
    )

    assert context.incident_id == "INC0000001"

    context.simulation_time += timedelta(seconds=30)

    resolve_generator = IncidentGenerator(
        ids=ids,
        behaviour=build_behaviour(
            profile_id="incident_resolved",
        ),
        event_history=created_events,
    )

    resolved_events = asyncio.run(
        collect_events(
            resolve_generator,
            context,
        )
    )

    assert len(resolved_events) == 1

    resolved_event = resolved_events[0]

    assert resolved_event.event_type == "itsm.incident.resolved"
    assert (
        resolved_event.data["incident"]["incident_id"]
        == "INC0000001"
    )
    assert resolved_event.data["incident"]["status"] == "resolved"
    assert resolved_event.source_domain == SourceDomain.INCIDENT


def test_incident_receives_central_incident_id() -> None:
    context = build_context()

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert (
        events[0].data["incident"]["incident_id"]
        == "INC0000001"
    )

    assert context.incident_id == "INC0000001"


def test_created_incident_is_open() -> None:
    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    incident = events[0].data["incident"]

    assert incident["status"] == "open"
    assert incident["resolved_at"] is None


def test_incident_preserves_change_and_run_correlation() -> None:
    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    event = events[0]

    assert event.scenario_id == "TEST-INC-01"
    assert event.run_id == "RUN0000001"
    assert event.chg_id == "CHG0000001"
    assert event.source_domain == SourceDomain.INCIDENT
    assert event.business_stream == "payments"
    assert event.service == "payment_service"
    assert event.component == "payment_api"


def test_incident_timestamp_matches_event_time() -> None:
    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    event = events[0]

    incident_time = datetime.fromisoformat(
        event.data["incident"]["created_at"]
    )

    assert incident_time == event.event_time


def test_incident_uses_scenario_sequence() -> None:
    context = build_context()

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events[0].sequence_number == 1
    assert context.sequence_number == 1


def test_no_incident_profile_generates_no_event() -> None:
    context = build_context()

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="no_incident",
        ),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []
    assert context.incident_id is None
    assert context.sequence_number == 0


def test_generator_does_not_run_outside_behaviour_state() -> None:
    context = build_context(
        state=OperationalState.NORMAL,
    )

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []
    assert context.incident_id is None
    assert context.sequence_number == 0


def test_custom_incident_definition_is_supported() -> None:
    incident = IncidentDefinition(
        title="Database connectivity failure",
        description="Database connections are failing.",
        severity=IncidentSeverity.CRITICAL,
        component_scoped=False,
        link_to_change=True,
    )

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        incident=incident,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    data = events[0].data["incident"]

    assert data["title"] == "Database connectivity failure"
    assert data["severity"] == "critical"
    assert data["component"] is None


def test_incident_can_be_unlinked_from_change() -> None:
    incident = IncidentDefinition(
        title="Unrelated infrastructure incident",
        severity=IncidentSeverity.MEDIUM,
        component_scoped=False,
        link_to_change=False,
    )

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        incident=incident,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert events[0].chg_id is None
    assert (
        events[0].data["incident"]["chg_id"]
        is None
    )


def test_generator_rejects_wrong_source_domain() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id="incident_created",
    )

    with pytest.raises(
        ValueError,
        match="requires an Incident behaviour",
    ):
        IncidentGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
        )


def test_generator_rejects_unknown_profile() -> None:
    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="unknown_incident_profile",
        ),
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Incident behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )