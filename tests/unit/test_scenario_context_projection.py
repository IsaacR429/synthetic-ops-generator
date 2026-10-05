from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionTarget,
)


def build_context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-05",
        run_id="RUN0000001",
        chg_id=None,
        business_stream="core_banking",
        service="account_service",
        component="account_database",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.HIGH,
        scenario_state=OperationalState.INITIALISING,
        simulation_time=datetime(
            2026,
            10,
            5,
            10,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def test_flat_context_contract_is_preserved() -> None:
    context = build_context()

    assert context.scenario_id == "BANK-05"
    assert context.run_id == "RUN0000001"
    assert context.chg_id is None

    assert context.business_stream == "core_banking"
    assert context.service == "account_service"
    assert context.component == "account_database"

    assert context.environment == Environment.PRODUCTION
    assert context.risk == RiskLevel.HIGH

    assert context.sequence_number == 0
    assert context.random_seed == 42


def test_context_serialization_remains_flat() -> None:
    context = build_context()

    payload = context.model_dump()

    assert "execution_state" not in payload
    assert "target" not in payload

    assert payload["scenario_id"] == "BANK-05"
    assert payload["run_id"] == "RUN0000001"
    assert payload["service"] == "account_service"
    assert payload["component"] == "account_database"
    assert payload["sequence_number"] == 0


def test_for_target_preserves_run_identity() -> None:
    context = build_context()

    projected = context.for_target(
        ScenarioExecutionTarget(
            business_stream="payments",
            service="payment_service",
            component=None,
            environment=Environment.PRODUCTION,
        )
    )

    assert projected.scenario_id == context.scenario_id
    assert projected.run_id == context.run_id
    assert projected.chg_id == context.chg_id
    assert projected.risk == context.risk
    assert projected.random_seed == context.random_seed

    assert context.service == "account_service"
    assert projected.service == "payment_service"

    assert context.component == "account_database"
    assert projected.component is None


def test_projected_contexts_share_sequence() -> None:
    context = build_context()

    projected = context.for_target(
        ScenarioExecutionTarget(
            business_stream="payments",
            service="payment_service",
            environment=Environment.PRODUCTION,
        )
    )

    assert context.next_sequence() == 1
    assert projected.next_sequence() == 2
    assert context.next_sequence() == 3

    assert context.sequence_number == 3
    assert projected.sequence_number == 3


def test_projected_contexts_share_lifecycle_state() -> None:
    context = build_context()

    projected = context.for_target(
        ScenarioExecutionTarget(
            business_stream="payments",
            service="payment_service",
            environment=Environment.PRODUCTION,
        )
    )

    new_time = (
        context.simulation_time
        + timedelta(seconds=30)
    )

    projected.scenario_state = OperationalState.DEGRADED
    projected.simulation_time = new_time

    assert (
        context.scenario_state
        == OperationalState.DEGRADED
    )
    assert context.simulation_time == new_time


def test_projected_contexts_share_correlations() -> None:
    context = build_context()

    projected = context.for_target(
        ScenarioExecutionTarget(
            business_stream="payments",
            service="payment_service",
            environment=Environment.PRODUCTION,
        )
    )

    context.deployment_id = "DEP0000001"
    projected.incident_id = "INC0000001"

    assert projected.deployment_id == "DEP0000001"
    assert context.incident_id == "INC0000001"


def test_for_target_shares_execution_state_object() -> None:
    context = build_context()

    projected = context.for_target(
        ScenarioExecutionTarget(
            business_stream="digital_banking",
            service="mobile_banking_service",
            component="mobile_api",
            environment=Environment.PRODUCTION,
        )
    )

    assert (
        projected.execution_state
        is context.execution_state
    )

    assert projected.target is not context.target
