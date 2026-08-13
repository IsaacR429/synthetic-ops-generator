import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.incident import (
    IncidentGenerator,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)

BASE_TIME = datetime(
    2026,
    8,
    13,
    10,
    0,
    tzinfo=UTC,
)


def build_context(
    *,
    state: OperationalState,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-INCIDENT-LIFECYCLE",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str,
    state: OperationalState,
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.INCIDENT,
        during_state=state,
        profile_id=profile_id,
    )


async def collect_events(
    generator: IncidentGenerator,
    context: ScenarioContext,
):
    events = []

    async for event in generator.generate(context):
        events.append(event)

        context.simulation_time = (
            context.simulation_time
            + timedelta(seconds=5)
        )

    return events


def test_incident_resolution_reuses_incident_id() -> None:
    ids = IdFactory()

    context = build_context(
        state=OperationalState.DEGRADED,
    )

    history = []

    create_generator = IncidentGenerator(
        ids=ids,
        behaviour=build_behaviour(
            profile_id="incident_created",
            state=OperationalState.DEGRADED,
        ),
    )

    created_events = asyncio.run(
        collect_events(
            create_generator,
            context,
        )
    )

    history.extend(created_events)

    assert context.incident_id == "INC0000001"

    context.scenario_state = OperationalState.RECOVERY

    resolve_generator = IncidentGenerator(
        ids=ids,
        behaviour=build_behaviour(
            profile_id="incident_resolved",
            state=OperationalState.RECOVERY,
        ),
        event_history=history,
    )

    resolved_events = asyncio.run(
        collect_events(
            resolve_generator,
            context,
        )
    )

    assert len(resolved_events) == 1

    resolved = resolved_events[0].data["incident"]

    assert resolved["incident_id"] == "INC0000001"
    assert resolved["status"] == "resolved"


def test_incident_resolution_preserves_original_incident() -> None:
    ids = IdFactory()

    context = build_context(
        state=OperationalState.DEGRADED,
    )

    create_generator = IncidentGenerator(
        ids=ids,
        behaviour=build_behaviour(
            profile_id="incident_created",
            state=OperationalState.DEGRADED,
        ),
    )

    created_events = asyncio.run(
        collect_events(
            create_generator,
            context,
        )
    )

    created = created_events[0].data["incident"]

    context.scenario_state = OperationalState.RECOVERY

    resolve_generator = IncidentGenerator(
        ids=ids,
        behaviour=build_behaviour(
            profile_id="incident_resolved",
            state=OperationalState.RECOVERY,
        ),
        event_history=created_events,
    )

    resolved_events = asyncio.run(
        collect_events(
            resolve_generator,
            context,
        )
    )

    resolved = resolved_events[0].data["incident"]

    assert resolved["chg_id"] == created["chg_id"]
    assert resolved["service"] == created["service"]
    assert resolved["component"] == created["component"]
    assert resolved["severity"] == created["severity"]
    assert resolved["created_at"] == created["created_at"]

    assert resolved["resolved_at"] is not None


def test_resolution_requires_existing_incident_id() -> None:
    context = build_context(
        state=OperationalState.RECOVERY,
    )

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="incident_resolved",
            state=OperationalState.RECOVERY,
        ),
        event_history=[],
    )

    with pytest.raises(
        ValueError,
        match="existing Incident ID",
    ):
        asyncio.run(
            collect_events(
                generator,
                context,
            )
        )


def test_resolution_requires_creation_event() -> None:
    context = build_context(
        state=OperationalState.RECOVERY,
    )
    context.incident_id = "INC0000001"

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="incident_resolved",
            state=OperationalState.RECOVERY,
        ),
        event_history=[],
    )

    with pytest.raises(
        ValueError,
        match="creation event",
    ):
        asyncio.run(
            collect_events(
                generator,
                context,
            )
        )


def test_resolution_does_not_run_in_wrong_state() -> None:
    context = build_context(
        state=OperationalState.NORMAL,
    )
    context.incident_id = "INC0000001"

    generator = IncidentGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            profile_id="incident_resolved",
            state=OperationalState.RECOVERY,
        ),
        event_history=[],
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []