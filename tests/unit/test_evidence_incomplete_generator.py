import asyncio
from datetime import UTC, datetime

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.evidence import EvidenceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def event_time() -> datetime:
    return datetime(
        2026,
        8,
        13,
        10,
        0,
        tzinfo=UTC,
    )


def build_source_event(
    *,
    ids: IdFactory,
    sequence_number: int,
    event_type: str,
    state: OperationalState,
    component: str | None = "claims_api",
) -> GeneratedEvent:
    data = {
        "scenario_state": state.value,
    }

    if event_type == "metric.observed":
        data = {
            "metric": {
                "scenario_state": state.value,
            },
        }

    return GeneratedEvent(
        event_id=ids.event_id(),
        event_type=event_type,
        event_time=event_time(),
        source_system="synthetic_source",
        scenario_id="INS-03",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="claims",
        service="claims_service",
        component=component,
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data=data,
    )


def build_history_without_approval(
    ids: IdFactory,
) -> list[GeneratedEvent]:
    events = []

    event_specs = [
        (
            "infrastructure_test.passed",
            OperationalState.NORMAL,
        ),
        (
            "infrastructure_test.passed",
            OperationalState.NORMAL,
        ),
        (
            "cicd.deployment.completed",
            OperationalState.IMPLEMENTING,
        ),
        (
            "application_test.passed",
            OperationalState.OBSERVING,
        ),
        (
            "application_test.passed",
            OperationalState.OBSERVING,
        ),
        (
            "metric.observed",
            OperationalState.NORMAL,
        ),
        (
            "metric.observed",
            OperationalState.NORMAL,
        ),
        (
            "metric.observed",
            OperationalState.OBSERVING,
        ),
        (
            "metric.observed",
            OperationalState.OBSERVING,
        ),
    ]

    for index, (
        event_type,
        state,
    ) in enumerate(
        event_specs,
        start=1,
    ):
        events.append(
            build_source_event(
                ids=ids,
                sequence_number=index,
                event_type=event_type,
                state=state,
            )
        )

    return events


def build_context(
    *,
    sequence_number: int = 9,
    state: OperationalState = OperationalState.OBSERVING,
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
        simulation_time=event_time(),
        sequence_number=sequence_number,
        random_seed=42,
    )


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.EVIDENCE,
        during_state=OperationalState.OBSERVING,
        profile_id="incomplete_validation_evidence",
    )


async def collect_events(
    generator: EvidenceGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_incomplete_validation_evidence_generates_five_events() -> None:
    ids = IdFactory()
    event_history = build_history_without_approval(ids)

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(),
        event_history=event_history,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 5

    assert [
        event.data["evidence"]["evidence_type"]
        for event in events
    ] == [
        "infrastructure_validation",
        "deployment_result",
        "application_validation",
        "pre_change_baseline",
        "post_change_observation",
    ]

    assert not any(
        event.data["evidence"]["evidence_type"]
        == "change_approval"
        for event in events
    )

    assert {
        event.data["behaviour_profile_id"]
        for event in events
    } == {
        "incomplete_validation_evidence"
    }

    history_event_ids = {
        event.event_id
        for event in event_history
    }

    for event in events:
        evidence = event.data["evidence"]

        assert evidence["source_event_ids"]

        assert set(
            evidence["source_event_ids"]
        ).issubset(history_event_ids)
