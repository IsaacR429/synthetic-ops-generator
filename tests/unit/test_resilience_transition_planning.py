import pytest
from pydantic import ValidationError

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.domain.enums import Environment, SourceDomain
from synthetic_ops_generator.topology.models import ServiceInstance
from synthetic_ops_generator.scenarios.execution_plan import (
    ScenarioExecutionPlanningError,
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioResilienceTransition,
)


def load_bank_alpha():
    return load_enterprise(
        "config/enterprises/bank_alpha"
    )


def load_bank_scenario():
    return load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )


def build_resilience_behaviour(
    *,
    execution_node_id: str | None = "payment_api_primary",
    to_execution_node_id: str | None = "payment_api_secondary",
) -> ScenarioBehaviour:
    scenario = load_bank_scenario()

    transition = (
        ScenarioResilienceTransition(
            to_execution_node_id=to_execution_node_id
        )
        if to_execution_node_id is not None
        else None
    )

    return ScenarioBehaviour(
        behaviour_id="fixture_test_resilience_transition_planning_01",
        source=SourceDomain.RESILIENCE,
        during_state=scenario.behaviours[0].during_state,
        profile_id="failover_initiated",
        execution_node_id=execution_node_id,
        resilience_transition=transition,
    )


def build_single_behaviour_scenario(
    behaviour: ScenarioBehaviour,
):
    scenario = load_bank_scenario()

    return scenario.model_copy(
        update={
            "behaviours": [
                behaviour,
            ],
        }
    )


def test_resilience_transition_accepts_destination_execution_node() -> None:
    transition = ScenarioResilienceTransition(
        to_execution_node_id="payment_api_secondary"
    )

    assert (
        transition.to_execution_node_id
        == "payment_api_secondary"
    )


def test_resilience_transition_rejects_blank_destination_node() -> None:
    with pytest.raises(ValidationError):
        ScenarioResilienceTransition(
            to_execution_node_id=" "
        )


def test_non_resilience_behaviour_rejects_resilience_transition() -> None:
    scenario = load_bank_scenario()

    with pytest.raises(
        ValidationError,
        match=(
            "Resilience transition is only valid "
            "for Resilience behaviour"
        ),
    ):
        ScenarioBehaviour(
            behaviour_id="fixture_test_resilience_transition_planning_02",
            source=SourceDomain.LOG,
            during_state=scenario.behaviours[0].during_state,
            profile_id="normal_operational_logs",
            execution_node_id="payment_api_primary",
            resilience_transition=(
                ScenarioResilienceTransition(
                    to_execution_node_id=(
                        "payment_api_secondary"
                    )
                )
            ),
        )


def test_resilience_transition_requires_source_execution_node() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Resilience transition requires "
            "execution_node_id"
        ),
    ):
        build_resilience_behaviour(
            execution_node_id=None,
        )


def test_resilience_behaviour_can_omit_transition() -> None:
    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_secondary",
        to_execution_node_id=None,
    )

    assert behaviour.resilience_transition is None
    assert (
        behaviour.execution_node_id
        == "payment_api_secondary"
    )


def test_execution_plan_resolves_resilience_source_and_destination() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour()

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    assert len(plan.entries) == 1

    entry = plan.entries[0]

    assert entry.execution_target is not None
    assert (
        entry.execution_target.service_instance_id
        == "payment_api_primary"
    )
    assert entry.execution_target.site_id == "bank_primary"

    assert (
        entry.resilience_transition_target
        is not None
    )
    assert (
        entry.resilience_transition_target.service_instance_id
        == "payment_api_secondary"
    )
    assert (
        entry.resilience_transition_target.site_id
        == "bank_secondary"
    )


def test_execution_plan_rejects_unknown_resilience_destination() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour(
        to_execution_node_id="missing_resilience_peer",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="missing_resilience_peer",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_resilience_without_transition_has_no_peer_target() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_secondary",
        to_execution_node_id=None,
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    entry = plan.entries[0]

    assert entry.execution_target is not None
    assert (
        entry.execution_target.service_instance_id
        == "payment_api_secondary"
    )
    assert entry.resilience_transition_target is None


def test_legacy_execution_plan_has_no_resilience_peer_targets() -> None:
    enterprise = load_bank_alpha()
    scenario = load_bank_scenario()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    assert all(
        entry.resilience_transition_target is None
        for entry in plan.entries
    )



def test_execution_plan_rejects_resilience_transition_from_component_target() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api",
        to_execution_node_id="payment_api_secondary",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match=(
            "source must resolve to "
            "a Service Instance"
        ),
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_resilience_transition_to_component_target() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_primary",
        to_execution_node_id="payment_api",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match=(
            "destination must resolve to "
            "a Service Instance"
        ),
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_resilience_transition_to_same_instance() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_primary",
        to_execution_node_id="payment_api_primary",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="instances must differ",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )



def test_execution_plan_rejects_resilience_transition_across_services() -> None:
    enterprise = load_bank_alpha()

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_primary",
        to_execution_node_id="account_database_secondary",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="same Service",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_resilience_transition_across_components() -> None:
    enterprise = load_bank_alpha().model_copy(
        deep=True
    )

    payment_worker = next(
        component
        for component in enterprise.components
        if component.component_id == "payment_worker"
    )

    assert (
        payment_worker.service_id
        == "payment_service"
    )
    assert (
        payment_worker.environment
        == Environment.PRODUCTION
    )

    enterprise.service_instances.append(
        ServiceInstance(
            instance_id="payment_worker_secondary",
            service_id="payment_service",
            component_id=payment_worker.component_id,
            site_id="bank_secondary",
            environment=Environment.PRODUCTION,
        )
    )

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_primary",
        to_execution_node_id="payment_worker_secondary",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="same Component",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_allows_same_site_distinct_resilience_instances() -> None:
    enterprise = load_bank_alpha().model_copy(
        deep=True
    )

    enterprise.service_instances.append(
        ServiceInstance(
            instance_id="payment_api_primary_peer",
            service_id="payment_service",
            component_id="payment_api",
            site_id="bank_primary",
            environment=Environment.PRODUCTION,
        )
    )

    behaviour = build_resilience_behaviour(
        execution_node_id="payment_api_primary",
        to_execution_node_id="payment_api_primary_peer",
    )

    scenario = build_single_behaviour_scenario(
        behaviour
    )

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    entry = plan.entries[0]

    assert entry.execution_target is not None
    assert (
        entry.resilience_transition_target
        is not None
    )

    assert (
        entry.execution_target.site_id
        == "bank_primary"
    )
    assert (
        entry.resilience_transition_target.site_id
        == "bank_primary"
    )

    assert (
        entry.execution_target.service_instance_id
        != entry.resilience_transition_target.service_instance_id
    )
