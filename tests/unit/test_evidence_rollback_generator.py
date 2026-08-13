import asyncio
from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.evidence import (
    EvidenceGenerator,
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


def build_context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-ROLLBACK-EVIDENCE",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=OperationalState.RECOVERY,
        simulation_time=(
            BASE_TIME
            + timedelta(minutes=10)
        ),
        sequence_number=11,
        random_seed=42,
    )


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.EVIDENCE,
        during_state=OperationalState.RECOVERY,
        profile_id="rollback_validation_evidence",
    )


def source_event(
    *,
    event_id: str,
    event_type: str,
    sequence_number: int,
    state: OperationalState,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type=event_type,
        event_time=(
            BASE_TIME
            + timedelta(
                seconds=sequence_number * 5
            )
        ),
        source_system="synthetic_test",
        scenario_id="TEST-ROLLBACK-EVIDENCE",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "scenario_state": state.value,
        },
    )


def build_history() -> list[GeneratedEvent]:
    return [
        source_event(
            event_id="EVT0000001",
            event_type="itsm.approval.approved",
            sequence_number=1,
            state=OperationalState.NORMAL,
        ),
        source_event(
            event_id="EVT0000002",
            event_type="infrastructure_test.passed",
            sequence_number=2,
            state=OperationalState.NORMAL,
        ),
        source_event(
            event_id="EVT0000003",
            event_type="cicd.deployment.completed",
            sequence_number=3,
            state=OperationalState.IMPLEMENTING,
        ),
        source_event(
            event_id="EVT0000004",
            event_type="application_test.failed",
            sequence_number=4,
            state=OperationalState.OBSERVING,
        ),
        source_event(
            event_id="EVT0000005",
            event_type="metric.observed",
            sequence_number=5,
            state=OperationalState.DEGRADED,
        ),
        source_event(
            event_id="EVT0000006",
            event_type="log.observed",
            sequence_number=6,
            state=OperationalState.DEGRADED,
        ),
        source_event(
            event_id="EVT0000007",
            event_type="itsm.incident.created",
            sequence_number=7,
            state=OperationalState.DEGRADED,
        ),
        source_event(
            event_id="EVT0000008",
            event_type=(
                "cicd.deployment.rollback_completed"
            ),
            sequence_number=8,
            state=OperationalState.ROLLBACK,
        ),
        source_event(
            event_id="EVT0000009",
            event_type="metric.observed",
            sequence_number=9,
            state=OperationalState.RECOVERY,
        ),
        source_event(
            event_id="EVT0000010",
            event_type="log.observed",
            sequence_number=10,
            state=OperationalState.RECOVERY,
        ),
        source_event(
            event_id="EVT0000011",
            event_type="itsm.incident.resolved",
            sequence_number=11,
            state=OperationalState.RECOVERY,
        ),
    ]


async def collect_events(
    generator: EvidenceGenerator,
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


def test_rollback_evidence_generates_expected_types() -> None:
    generator = EvidenceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        event_history=build_history(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 9

    assert [
        event.data["evidence"]["evidence_type"]
        for event in events
    ] == [
        "change_approval",
        "infrastructure_validation",
        "deployment_result",
        "application_regression",
        "degraded_observation",
        "incident_record",
        "rollback_result",
        "recovery_observation",
        "incident_resolution",
    ]


def test_degradation_evidence_uses_only_degraded_sources() -> None:
    generator = EvidenceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        event_history=build_history(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    degradation = next(
        event.data["evidence"]
        for event in events
        if (
            event.data["evidence"]["evidence_type"]
            == "degraded_observation"
        )
    )

    assert degradation["source_event_ids"] == [
        "EVT0000005",
        "EVT0000006",
    ]


def test_recovery_evidence_uses_only_recovery_sources() -> None:
    generator = EvidenceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        event_history=build_history(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    recovery = next(
        event.data["evidence"]
        for event in events
        if (
            event.data["evidence"]["evidence_type"]
            == "recovery_observation"
        )
    )

    assert recovery["source_event_ids"] == [
        "EVT0000009",
        "EVT0000010",
    ]


def test_rollback_evidence_references_existing_prior_events() -> None:
    history = build_history()

    generator = EvidenceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        event_history=history,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    known_ids = {
        event.event_id
        for event in history
    }

    for evidence_event in events:
        references = (
            evidence_event.data["evidence"][
                "source_event_ids"
            ]
        )

        assert references

        assert set(references).issubset(
            known_ids
        )

        referenced_sequences = [
            event.sequence_number
            for event in history
            if event.event_id in references
        ]

        assert all(
            sequence
            < evidence_event.sequence_number
            for sequence in referenced_sequences
        )