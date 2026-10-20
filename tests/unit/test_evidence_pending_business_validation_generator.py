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
from synthetic_ops_generator.scenarios.profile_contracts import (
    SUPPORTED_PROFILES_BY_SOURCE,
)


PROFILE_ID = "pending_business_validation_evidence"


def event_time() -> datetime:
    return datetime(
        2026,
        8,
        14,
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

    if event_type == "manual_validation.requested":
        data = {
            "validation": {
                "validation_type": "business_validation",
                "mandatory": True,
                "status": "pending",
                "result": None,
                "completed_at": None,
            },
            "scenario_state": state.value,
        }

    return GeneratedEvent(
        event_id=ids.event_id(),
        event_type=event_type,
        event_time=event_time(),
        source_system="synthetic_source",
        scenario_id="INS-05",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data=data,
    )


def build_history(
    ids: IdFactory,
) -> list[GeneratedEvent]:
    specs = (
        (
            "itsm.approval.approved",
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
            "metric.observed",
            OperationalState.NORMAL,
        ),
        (
            "metric.observed",
            OperationalState.OBSERVING,
        ),
        (
            "manual_validation.requested",
            OperationalState.OBSERVING,
        ),
    )

    return [
        build_source_event(
            ids=ids,
            sequence_number=index,
            event_type=event_type,
            state=state,
        )
        for index, (
            event_type,
            state,
        ) in enumerate(
            specs,
            start=1,
        )
    ]


def build_context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="INS-05",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.HIGH,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=event_time(),
        sequence_number=7,
        random_seed=42,
    )


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id=(
            "fixture_pending_business_validation_evidence"
        ),
        source=SourceDomain.EVIDENCE,
        during_state=OperationalState.OBSERVING,
        profile_id=PROFILE_ID,
    )


async def collect_events(
    generator: EvidenceGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_pending_business_validation_evidence_profile_is_supported() -> None:
    assert (
        PROFILE_ID
        in SUPPORTED_PROFILES_BY_SOURCE[
            SourceDomain.EVIDENCE
        ]
    )


def test_pending_business_validation_evidence_preserves_complete_package_and_request() -> None:
    ids = IdFactory()
    history = build_history(ids)

    manual_request = next(
        event
        for event in history
        if (
            event.event_type
            == "manual_validation.requested"
        )
    )

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(),
        event_history=history,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    evidence_by_type = {
        event.data["evidence"]["evidence_type"]: event
        for event in events
    }

    assert set(evidence_by_type) == {
        "change_approval",
        "infrastructure_validation",
        "deployment_result",
        "application_validation",
        "pre_change_baseline",
        "post_change_observation",
        "business_validation_request",
    }

    request_evidence = evidence_by_type[
        "business_validation_request"
    ]

    assert request_evidence.data[
        "evidence"
    ]["source_event_ids"] == [
        manual_request.event_id
    ]

    assert {
        event.data["behaviour_profile_id"]
        for event in events
    } == {
        PROFILE_ID,
    }

    assert not any(
        event.data["evidence"]["evidence_type"]
        == "missing_business_validation_completion"
        for event in events
    )
