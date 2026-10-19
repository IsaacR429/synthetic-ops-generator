from __future__ import annotations

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.domain.resilience import (
    ReplicationStatus,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    ScenarioExecutionPlanningError,
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioResilienceReplication,
    ScenarioResilienceTransition,
)
from synthetic_ops_generator.topology.models import (
    ServiceInstance,
)


def load_bank_alpha():
    return load_enterprise(
        "config/enterprises/bank_alpha"
    )


def load_bank_scenario():
    return load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )


def build_replication_behaviour(
    *,
    execution_node_id: str | None = (
        "payment_api_primary"
    ),
    to_execution_node_id: str = (
        "payment_api_secondary"
    ),
    replication_status: ReplicationStatus = (
        ReplicationStatus.LAGGING
    ),
    last_successful_replication_offset_seconds: (
        float | None
    ) = 120.0,
) -> ScenarioBehaviour:
    scenario = load_bank_scenario()

    return ScenarioBehaviour(
        behaviour_id=(
            "fixture_test_resilience_replication_planning_01"
        ),
        source=SourceDomain.RESILIENCE,
        during_state=scenario.behaviours[0].during_state,
        profile_id="replication_observed",
        execution_node_id=execution_node_id,
        resilience_replication=(
            ScenarioResilienceReplication(
                to_execution_node_id=(
                    to_execution_node_id
                ),
                replication_status=replication_status,
                last_successful_replication_offset_seconds=(
                    last_successful_replication_offset_seconds
                ),
            )
        ),
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


def test_replication_contract_accepts_factual_configuration() -> None:
    replication = ScenarioResilienceReplication(
        to_execution_node_id="payment_api_secondary",
        replication_status=ReplicationStatus.LAGGING,
        last_successful_replication_offset_seconds=120.0,
    )

    assert (
        replication.to_execution_node_id
        == "payment_api_secondary"
    )

    assert (
        replication.replication_status
        == ReplicationStatus.LAGGING
    )

    assert (
        replication.last_successful_replication_offset_seconds
        == 120.0
    )


def test_replication_contract_allows_unknown_last_success() -> None:
    replication = ScenarioResilienceReplication(
        to_execution_node_id="payment_api_secondary",
        replication_status=ReplicationStatus.UNKNOWN,
        last_successful_replication_offset_seconds=None,
    )

    assert (
        replication.last_successful_replication_offset_seconds
        is None
    )


def test_replication_contract_rejects_blank_destination() -> None:
    with pytest.raises(ValidationError):
        ScenarioResilienceReplication(
            to_execution_node_id=" ",
            replication_status=ReplicationStatus.LAGGING,
            last_successful_replication_offset_seconds=120.0,
        )


def test_replication_contract_rejects_negative_offset() -> None:
    with pytest.raises(ValidationError):
        ScenarioResilienceReplication(
            to_execution_node_id="payment_api_secondary",
            replication_status=ReplicationStatus.LAGGING,
            last_successful_replication_offset_seconds=-1.0,
        )


def test_non_resilience_behaviour_rejects_replication() -> None:
    scenario = load_bank_scenario()

    with pytest.raises(
        ValidationError,
        match=(
            "Resilience replication is only valid "
            "for Resilience behaviour"
        ),
    ):
        ScenarioBehaviour(
            behaviour_id=(
                "fixture_test_resilience_replication_planning_02"
            ),
            source=SourceDomain.LOG,
            during_state=scenario.behaviours[0].during_state,
            profile_id="normal_operational_logs",
            execution_node_id="payment_api_primary",
            resilience_replication=(
                ScenarioResilienceReplication(
                    to_execution_node_id=(
                        "payment_api_secondary"
                    ),
                    replication_status=(
                        ReplicationStatus.LAGGING
                    ),
                    last_successful_replication_offset_seconds=(
                        120.0
                    ),
                )
            ),
        )


def test_replication_requires_source_execution_node() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Resilience replication requires "
            "execution_node_id"
        ),
    ):
        build_replication_behaviour(
            execution_node_id=None,
        )


def test_behaviour_rejects_transition_and_replication_together() -> None:
    scenario = load_bank_scenario()

    with pytest.raises(
        ValidationError,
        match=(
            "Resilience transition and replication "
            "cannot be configured together"
        ),
    ):
        ScenarioBehaviour(
            behaviour_id=(
                "fixture_test_resilience_replication_planning_03"
            ),
            source=SourceDomain.RESILIENCE,
            during_state=scenario.behaviours[0].during_state,
            profile_id="replication_observed",
            execution_node_id="payment_api_primary",
            resilience_transition=(
                ScenarioResilienceTransition(
                    to_execution_node_id=(
                        "payment_api_secondary"
                    )
                )
            ),
            resilience_replication=(
                ScenarioResilienceReplication(
                    to_execution_node_id=(
                        "payment_api_secondary"
                    ),
                    replication_status=(
                        ReplicationStatus.LAGGING
                    ),
                    last_successful_replication_offset_seconds=(
                        120.0
                    ),
                )
            ),
        )


def test_execution_plan_resolves_replication_source_and_destination() -> None:
    enterprise = load_bank_alpha()

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour()
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
    assert (
        entry.execution_target.site_id
        == "bank_primary"
    )

    assert entry.resilience_replication_target is not None

    assert (
        entry.resilience_replication_target
        .service_instance_id
        == "payment_api_secondary"
    )
    assert (
        entry.resilience_replication_target.site_id
        == "bank_secondary"
    )


def test_execution_plan_rejects_unknown_replication_destination() -> None:
    enterprise = load_bank_alpha()

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            to_execution_node_id=(
                "missing_replication_peer"
            ),
        )
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="missing_replication_peer",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_replication_from_component_target() -> None:
    enterprise = load_bank_alpha()

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            execution_node_id="payment_api",
        )
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


def test_execution_plan_rejects_replication_to_component_target() -> None:
    enterprise = load_bank_alpha()

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            to_execution_node_id="payment_api",
        )
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


def test_execution_plan_rejects_replication_to_same_instance() -> None:
    enterprise = load_bank_alpha()

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            to_execution_node_id=(
                "payment_api_primary"
            ),
        )
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="instances must differ",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_replication_across_services() -> None:
    enterprise = load_bank_alpha()

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            to_execution_node_id=(
                "account_database_secondary"
            ),
        )
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="same Service",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_rejects_replication_across_components() -> None:
    enterprise = load_bank_alpha().model_copy(
        deep=True
    )

    payment_worker = next(
        component
        for component in enterprise.components
        if component.component_id == "payment_worker"
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

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            to_execution_node_id=(
                "payment_worker_secondary"
            ),
        )
    )

    with pytest.raises(
        ScenarioExecutionPlanningError,
        match="same Component",
    ):
        build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )


def test_execution_plan_allows_same_site_distinct_replication_instances() -> None:
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

    scenario = build_single_behaviour_scenario(
        build_replication_behaviour(
            to_execution_node_id=(
                "payment_api_primary_peer"
            ),
        )
    )

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    entry = plan.entries[0]

    assert entry.execution_target is not None
    assert entry.resilience_replication_target is not None

    assert (
        entry.execution_target.site_id
        == "bank_primary"
    )
    assert (
        entry.resilience_replication_target.site_id
        == "bank_primary"
    )

    assert (
        entry.execution_target.service_instance_id
        != entry.resilience_replication_target
        .service_instance_id
    )


def test_replication_configuration_contains_no_rpo_interpretation() -> None:
    replication = ScenarioResilienceReplication(
        to_execution_node_id="payment_api_secondary",
        replication_status=ReplicationStatus.LAGGING,
        last_successful_replication_offset_seconds=120.0,
    )

    payload = replication.model_dump()

    forbidden = {
        "rpo_actual",
        "rpo_met",
        "data_loss",
        "dr_success",
        "compliant",
        "decision",
    }

    assert forbidden.isdisjoint(payload)
