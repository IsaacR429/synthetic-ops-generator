import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.domain.enterprise import Component
from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    ScenarioExecutionPlanningError,
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)


def test_execution_plan_preserves_legacy_base_target() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )
    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )
    assert len(plan.entries) == len(
        scenario.behaviours
    )
    assert all(
        entry.execution_target is None
        for entry in plan.entries
    )


def test_execution_plan_resolves_cross_service_component() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )
    behaviour = scenario.behaviours[0]
    behaviour.execution_node_id = (
        "account_database"
    )
    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )
    target = plan.entries[0].execution_target
    assert target is not None
    assert target.business_stream == "core_banking"
    assert target.service == "account_service"
    assert target.component == "account_database"
    assert target.environment == scenario.target.environment


def test_execution_plan_rejects_unknown_node() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )
    scenario.behaviours[0].execution_node_id = (
        "missing_node"
    )
    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="missing_node",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_targeted_itsm_behaviour() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )
    itsm_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.ITSM
    )
    itsm_behaviour.execution_node_id = (
        "account_database"
    )
    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="ITSM behaviour must remain",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_normalizes_invalid_topology_error() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    enterprise.components.append(
        Component(
            component_id="payment_service",
            name="Ambiguous Component",
            component_type="api",
            service_id="payment_service",
            environment=Environment.PRODUCTION,
        )
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )
    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="globally unique",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )
