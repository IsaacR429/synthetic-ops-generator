from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import (
    Action,
    Criticality,
    Decision,
    Environment,
    Industry,
    OperationalState,
    Outcome,
    RiskLevel,
)
from synthetic_ops_generator.oracle.models import ExpectedScenarioResult
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioDefinition,
    ScenarioFamily,
    ScenarioTarget,
    ScenarioTrigger,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.runner import ScenarioRunner


def build_enterprise() -> Enterprise:
    return Enterprise(
        enterprise_id="bank_alpha",
        name="Bank Alpha",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(
                stream_id="payments",
                name="Payments",
            )
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="Payments Operations",
                criticality=Criticality.CRITICAL,
            )
        ],
        components=[
            Component(
                component_id="payment_api",
                name="Payment API",
                component_type="api",
                service_id="payment_service",
                environment=Environment.PRODUCTION,
            )
        ],
    )


def build_scenario() -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id="BANK-01",
        name="Successful Payment Release",
        description="Healthy payment-service release.",
        family=ScenarioFamily.CHANGE_VALIDATION,
        industry=Industry.BANKING,
        target=ScenarioTarget(
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            component_ids=["payment_api"],
            environment=Environment.PRODUCTION,
        ),
        risk=RiskLevel.MEDIUM,
        initial_conditions=[
            "Change approved",
            "Payment Service healthy",
        ],
        trigger=ScenarioTrigger(
            source=SourceDomain.DEPLOYMENT,
            trigger_type="deployment",
            description="Deploy payment API.",
            artifact="payment-api",
            version="2.5.0",
        ),
        state_sequence=[
            OperationalState.INITIALISING,
            OperationalState.NORMAL,
            OperationalState.IMPLEMENTING,
            OperationalState.OBSERVING,
            OperationalState.COMPLETED,
        ],
        behaviours=[
            ScenarioBehaviour(
                source=SourceDomain.ITSM,
                during_state=OperationalState.NORMAL,
                profile_id="approved_change",
            ),
            ScenarioBehaviour(
                source=SourceDomain.DEPLOYMENT,
                during_state=OperationalState.IMPLEMENTING,
                profile_id="successful_deployment",
            ),
        ],
        expected_result=ExpectedScenarioResult(
            scenario_id="BANK-01",
            expected_decision=Decision.PASS,
            expected_action=Action.PROCEED,
            expected_outcome=Outcome.SUCCESSFUL,
        ),
    )


def test_runner_creates_scenario_context() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    context = runner.create_context(
        scenario=build_scenario(),
        enterprise=build_enterprise(),
        random_seed=42,
    )

    assert context.scenario_id == "BANK-01"
    assert context.run_id == "RUN0000001"
    assert context.chg_id == "CHG0000001"

    assert context.business_stream == "payments"
    assert context.service == "payment_service"
    assert context.component == "payment_api"

    assert context.environment == Environment.PRODUCTION
    assert context.risk == RiskLevel.MEDIUM

    assert context.scenario_state == OperationalState.INITIALISING
    assert context.simulation_time == start
    assert context.sequence_number == 0
    assert context.random_seed == 42


def test_runner_creates_unique_run_and_change_ids() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    scenario = build_scenario()
    enterprise = build_enterprise()

    first = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    second = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    assert first.run_id == "RUN0000001"
    assert second.run_id == "RUN0000002"

    assert first.chg_id == "CHG0000001"
    assert second.chg_id == "CHG0000002"


def test_runner_executes_bank_01_state_sequence() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    scenario = build_scenario()

    context = runner.create_context(
        scenario=scenario,
        enterprise=build_enterprise(),
        random_seed=42,
    )

    visited_states = runner.execute_state_sequence(
        scenario=scenario,
        context=context,
    )

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert context.scenario_state == OperationalState.COMPLETED


def test_runner_rejects_wrong_enterprise() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    runner = ScenarioRunner(
        ids=IdFactory(),
        clock=ManualSimulationClock(start),
    )

    wrong_enterprise = build_enterprise().model_copy(
        update={
            "enterprise_id": "wrong_bank",
        }
    )

    with pytest.raises(
        ValueError,
        match="Scenario target enterprise",
    ):
        runner.create_context(
            scenario=build_scenario(),
            enterprise=wrong_enterprise,
            random_seed=42,
        )