import asyncio
from datetime import UTC, datetime

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def build_context(
    *,
    state: OperationalState = OperationalState.NORMAL,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="INS-03",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
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


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.ITSM,
        during_state=OperationalState.NORMAL,
        profile_id="missing_required_approval",
    )


async def collect_events(
    generator: ITSMGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_missing_required_approval_generates_expected_events() -> None:
    context = build_context()

    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Claims Operations",
        component_ids=["claims_api", "claims_database"],
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert [
        event.event_type
        for event in events
    ] == [
        "itsm.change.created",
        "itsm.approval.missing",
    ]

    change = events[0].data["change"]
    approval = events[1].data["approval"]

    assert change["status"] == "created"
    assert approval["status"] == "missing"
    assert approval["chg_id"] == context.chg_id

    assert (
        events[1].data["change_status"]
        == "created"
    )

    assert not any(
        event.event_type == "itsm.approval.approved"
        for event in events
    )

    assert {
        event.scenario_id
        for event in events
    } == {context.scenario_id}

    assert {
        event.run_id
        for event in events
    } == {context.run_id}

    assert {
        event.chg_id
        for event in events
    } == {context.chg_id}
