import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.evidence import (
    EvidenceDefinition,
    EvidenceGenerator,
)
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
    component: str | None = "payment_api",
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
        scenario_id="TEST-EVD-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component=component,
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data=data,
    )


def build_history(
    ids: IdFactory,
) -> list[GeneratedEvent]:
    events = []

    event_specs = [
        (
            "itsm.approval.approved",
            OperationalState.NORMAL,
        ),
        (
            "infrastructure_test.passed",
            OperationalState.NORMAL,
        ),
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
    sequence_number: int = 14,
    state: OperationalState = OperationalState.OBSERVING,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-EVD-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=state,
        simulation_time=event_time(),
        sequence_number=sequence_number,
        random_seed=42,
    )


def build_behaviour(
    *,
    profile_id: str = "complete_validation_evidence",
) -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.EVIDENCE,
        during_state=OperationalState.OBSERVING,
        profile_id=profile_id,
    )


async def collect_events(
    generator: EvidenceGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_complete_validation_evidence_generates_six_events() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    assert len(events) == 6

    assert all(
        event.event_type == "evidence.captured"
        for event in events
    )


def test_expected_evidence_types_are_generated() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    assert [
        event.data["evidence"]["evidence_type"]
        for event in events
    ] == [
        "change_approval",
        "infrastructure_validation",
        "deployment_result",
        "application_validation",
        "pre_change_baseline",
        "post_change_observation",
    ]


def test_evidence_references_real_source_events() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    history_ids = {
        event.event_id
        for event in history
    }

    for event in events:
        references = set(
            event.data["evidence"]["source_event_ids"]
        )

        assert references
        assert references <= history_ids


def test_infrastructure_evidence_references_all_passed_checks() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    evidence = events[1].data["evidence"]

    assert len(evidence["source_event_ids"]) == 3


def test_application_evidence_references_all_passed_tests() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    evidence = events[3].data["evidence"]

    assert len(evidence["source_event_ids"]) == 3


def test_metric_evidence_separates_baseline_and_post_change() -> None:
    ids = IdFactory()
    history = build_history(ids)

    normal_metric_ids = {
        event.event_id
        for event in history
        if event.event_type == "metric.observed"
        and event.data["metric"]["scenario_state"] == "normal"
    }

    observing_metric_ids = {
        event.event_id
        for event in history
        if event.event_type == "metric.observed"
        and event.data["metric"]["scenario_state"] == "observing"
    }

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

    pre_change = set(
        events[4].data["evidence"]["source_event_ids"]
    )

    post_change = set(
        events[5].data["evidence"]["source_event_ids"]
    )

    assert pre_change == normal_metric_ids
    assert post_change == observing_metric_ids
    assert pre_change.isdisjoint(post_change)


def test_evidence_uses_central_evidence_ids() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    assert [
        event.data["evidence"]["evidence_id"]
        for event in events
    ] == [
        "EVD0000001",
        "EVD0000002",
        "EVD0000003",
        "EVD0000004",
        "EVD0000005",
        "EVD0000006",
    ]


def test_evidence_preserves_run_correlation() -> None:
    ids = IdFactory()
    history = build_history(ids)

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

    assert {
        event.scenario_id
        for event in events
    } == {"TEST-EVD-01"}

    assert {
        event.run_id
        for event in events
    } == {"RUN0000001"}

    assert {
        event.chg_id
        for event in events
    } == {"CHG0000001"}

    assert {
        event.source_domain
        for event in events
    } == {SourceDomain.EVIDENCE}


def test_evidence_uses_scenario_sequence() -> None:
    ids = IdFactory()
    history = build_history(ids)
    context = build_context()

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(),
        event_history=history,
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert [
        event.sequence_number
        for event in events
    ] == [15, 16, 17, 18, 19, 20]

    assert context.sequence_number == 20


def test_missing_required_source_events_is_rejected() -> None:
    ids = IdFactory()
    history = build_history(ids)

    history = [
        event
        for event in history
        if event.event_type
        != "cicd.deployment.completed"
    ]

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(),
        event_history=history,
    )

    with pytest.raises(
        ValueError,
        match="Missing source events for Evidence type",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )


def test_generator_does_not_run_outside_behaviour_state() -> None:
    ids = IdFactory()
    history = build_history(ids)

    context = build_context(
        state=OperationalState.NORMAL,
    )

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(),
        event_history=history,
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert events == []


def test_generator_rejects_wrong_source_domain() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id="complete_validation_evidence",
    )

    with pytest.raises(
        ValueError,
        match="requires an Evidence behaviour",
    ):
        EvidenceGenerator(
            ids=IdFactory(),
            behaviour=behaviour,
            event_history=[],
        )


def test_generator_rejects_unknown_profile() -> None:
    ids = IdFactory()
    history = build_history(ids)

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(
            profile_id="unknown_evidence_profile",
        ),
        event_history=history,
    )

    with pytest.raises(
        ValueError,
        match="Unsupported Evidence behaviour profile",
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )


def test_custom_evidence_definition_is_supported() -> None:
    ids = IdFactory()
    history = build_history(ids)

    definitions = (
        EvidenceDefinition(
            evidence_type="deployment_only",
            title="Deployment completion",
            event_types=(
                "cicd.deployment.completed",
            ),
        ),
    )

    generator = EvidenceGenerator(
        ids=ids,
        behaviour=build_behaviour(),
        event_history=history,
        definitions=definitions,
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 1

    assert (
        events[0].data["evidence"]["evidence_type"]
        == "deployment_only"
    )