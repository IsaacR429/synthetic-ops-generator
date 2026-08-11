import asyncio
from datetime import UTC, datetime

import pytest

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
        scenario_id="BANK-01",
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
            11,
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
        profile_id="approved_change",
    )


async def collect_events(
    generator: ITSMGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_approved_change_generates_two_itsm_events() -> None:
    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Payments Operations",
        component_ids=[
            "payment_api",
            "payment_database",
            "payment_worker",
        ],
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 2

    assert events[0].event_type == "itsm.change.created"
    assert events[1].event_type == "itsm.approval.approved"


def test_itsm_events_share_run_and_change_correlation() -> None:
    context = build_context()

    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Payments Operations",
        component_ids=["payment_api"],
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert {
        event.scenario_id for event in events
    } == {"BANK-01"}

    assert {
        event.run_id for event in events
    } == {"RUN0000001"}

    assert {
        event.chg_id for event in events
    } == {"CHG0000001"}

    assert {
        event.business_stream for event in events
    } == {"payments"}

    assert {
        event.service for event in events
    } == {"payment_service"}

    assert {
        event.environment for event in events
    } == {Environment.PRODUCTION}


def test_itsm_events_use_canonical_identifiers_and_sequence() -> None:
    context = build_context()

    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Payments Operations",
        component_ids=["payment_api"],
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events[0].event_id == "EVT0000001"
    assert events[1].event_id == "EVT0000002"

    assert events[0].sequence_number == 1
    assert events[1].sequence_number == 2

    assert context.sequence_number == 2


def test_change_event_contains_expected_domain_data() -> None:
    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Payments Operations",
        component_ids=[
            "payment_api",
            "payment_database",
        ],
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    change_data = events[0].data["change"]

    assert change_data["chg_id"] == "CHG0000001"
    assert change_data["business_stream"] == "payments"
    assert change_data["service"] == "payment_service"

    assert change_data["components"] == [
        "payment_api",
        "payment_database",
    ]

    assert change_data["risk"] == "medium"
    assert change_data["owner"] == "Payments Operations"
    assert change_data["environment"] == "production"
    assert change_data["status"] == "created"


def test_approval_event_contains_expected_domain_data() -> None:
    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Payments Operations",
        component_ids=["payment_api"],
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    approval_data = events[1].data["approval"]

    assert approval_data["approval_id"] == "APR0000001"
    assert approval_data["chg_id"] == "CHG0000001"
    assert approval_data["approval_type"] == "implementation"
    assert approval_data["status"] == "approved"
    assert approval_data["source"] == "synthetic_itsm"

    assert events[1].data["change_status"] == "approved"


def test_itsm_generator_does_not_generate_outside_behaviour_state() -> None:
    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        service_owner="Payments Operations",
        component_ids=["payment_api"],
    )

    context = build_context(
        state=OperationalState.IMPLEMENTING,
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []
    assert context.sequence_number == 0


def test_itsm_generator_rejects_non_itsm_behaviour() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.DEPLOYMENT,
        during_state=OperationalState.NORMAL,
        profile_id="successful_deployment",
    )

    with pytest.raises(
        ValueError,
        match="requires an ITSM behaviour",
    ):
        ITSMGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
            service_owner="Payments Operations",
            component_ids=["payment_api"],
        )


def test_itsm_generator_rejects_unknown_profile() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.ITSM,
        during_state=OperationalState.NORMAL,
        profile_id="unknown_profile",
    )

    generator = ITSMGenerator(
        ids=IdFactory(),
        behaviour=behaviour,
        service_owner="Payments Operations",
        component_ids=["payment_api"],
    )

    with pytest.raises(
        ValueError,
        match="Unsupported ITSM behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )