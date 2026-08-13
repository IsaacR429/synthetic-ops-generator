import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestDefinition,
    ApplicationTestGenerator,
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
    state: OperationalState = OperationalState.OBSERVING,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-APP-REGRESSION",
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


def build_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        source=SourceDomain.APPLICATION_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="mandatory_test_regression",
        description="Mandatory test fails with regression.",
    )


async def collect_events(
    generator: ApplicationTestGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_mandatory_test_regression_emits_planned_passed_and_failed_events() -> None:
    context = build_context()

    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    assert len(events) == 6

    assert [
        event.event_type
        for event in events
    ] == [
        "application_test.planned",
        "application_test.passed",
        "application_test.planned",
        "application_test.passed",
        "application_test.planned",
        "application_test.failed",
    ]


def test_regression_marks_last_mandatory_test_as_failed() -> None:
    context = build_context()

    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    failed_event = events[-1]
    test = failed_event.data["test"]

    assert test["status"] == "executed"
    assert test["result"] == "failed"
    assert (
        test["failure_reason"]
        == "Post-change application regression detected."
    )


def test_passed_tests_have_no_failure_reason() -> None:
    context = build_context()

    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            context,
        )
    )

    passed_executed_events = [
        events[1],
        events[3],
    ]

    for event in passed_executed_events:
        test = event.data["test"]
        assert test["result"] == "passed"
        assert test["failure_reason"] is None


def test_regression_requires_at_least_one_mandatory_test() -> None:
    context = build_context()

    tests = (
        ApplicationTestDefinition(
            test_type="optional_check",
            name="Optional check",
            mandatory=False,
        ),
    )

    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        tests=tests,
    )

    async def execute() -> None:
        async for _ in generator.generate(context):
            pass

    with pytest.raises(
        ValueError,
        match="Mandatory Test regression requires at least one mandatory Test",
    ):
        asyncio.run(execute())
