from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.state_machine import (
    ScenarioStateMachine,
)


def load_bank_alpha():
    return load_enterprise(
        "config/enterprises/bank_alpha"
    )


def load_bank_06():
    return load_scenario(
        "config/scenarios/banking/BANK-06.yaml"
    )


def test_bank_06_defines_explicit_payment_api_failover() -> None:
    scenario = load_bank_06()

    assert scenario.scenario_id == "BANK-06"

    resilience_behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.RESILIENCE
    ]

    assert [
        behaviour.profile_id
        for behaviour in resilience_behaviours
    ] == [
        "service_unavailable",
        "replication_observed",
        "failover_initiated",
        "traffic_switch_started",
        "traffic_switch_completed",
        "instance_activated",
        "service_available",
        "instance_serving",
        "service_available",
    ]

    transition_behaviours = [
        behaviour
        for behaviour in resilience_behaviours
        if behaviour.resilience_transition is not None
    ]

    assert [
        behaviour.profile_id
        for behaviour in transition_behaviours
    ] == [
        "failover_initiated",
        "traffic_switch_started",
        "traffic_switch_completed",
    ]

    for behaviour in transition_behaviours:
        assert (
            behaviour.execution_node_id
            == "payment_api_primary"
        )
        assert (
            behaviour.resilience_transition
            .to_execution_node_id
            == "payment_api_secondary"
        )

    replication_behaviours = [
        behaviour
        for behaviour in resilience_behaviours
        if behaviour.resilience_replication is not None
    ]

    assert len(replication_behaviours) == 1
    assert (
        replication_behaviours[0].profile_id
        == "replication_observed"
    )
    assert (
        replication_behaviours[0].execution_node_id
        == "payment_api_primary"
    )
    assert (
        replication_behaviours[0]
        .resilience_replication
        .to_execution_node_id
        == "payment_api_secondary"
    )


def test_bank_06_resilience_observations_are_bounded() -> None:
    scenario = load_bank_06()

    resilience_behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.RESILIENCE
    ]

    assert resilience_behaviours

    assert all(
        behaviour.continuous is False
        for behaviour in resilience_behaviours
    )


def test_bank_06_continuous_recovery_runs_on_secondary() -> None:
    scenario = load_bank_06()

    continuous_secondary = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.continuous
            and behaviour.execution_node_id
            == "payment_api_secondary"
        )
    ]

    assert continuous_secondary

    assert {
        behaviour.source
        for behaviour in continuous_secondary
    } == {
        SourceDomain.METRIC,
        SourceDomain.LOG,
    }


def test_bank_06_plan_resolves_primary_to_secondary_transition() -> None:
    scenario = load_bank_06()
    enterprise = load_bank_alpha()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    resilience_entries = [
        entry
        for entry in plan.entries
        if entry.behaviour.source
        == SourceDomain.RESILIENCE
    ]

    assert len(resilience_entries) == 9

    transition_entries = [
        entry
        for entry in resilience_entries
        if entry.resilience_transition_target is not None
    ]

    assert len(transition_entries) == 3

    for entry in transition_entries:
        assert entry.execution_target is not None
        assert (
            entry.execution_target.service_instance_id
            == "payment_api_primary"
        )
        assert (
            entry.execution_target.site_id
            == "bank_primary"
        )
        assert (
            entry.resilience_transition_target
            .service_instance_id
            == "payment_api_secondary"
        )
        assert (
            entry.resilience_transition_target.site_id
            == "bank_secondary"
        )

    replication_entries = [
        entry
        for entry in resilience_entries
        if entry.resilience_replication_target is not None
    ]

    assert len(replication_entries) == 1

    replication_entry = replication_entries[0]

    assert (
        replication_entry.execution_target
        .service_instance_id
        == "payment_api_primary"
    )
    assert (
        replication_entry.resilience_replication_target
        .service_instance_id
        == "payment_api_secondary"
    )


def test_bank_06_primary_recovery_is_observed_without_failback() -> None:
    scenario = load_bank_06()

    primary_recovery = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.execution_node_id
            == "payment_api_primary"
            and behaviour.during_state.value
            == "recovery"
        )
    ]

    assert {
        behaviour.profile_id
        for behaviour in primary_recovery
    } >= {
        "all_required_checks_pass",
        "operational_recovery",
    }

    resilience_profiles = {
        behaviour.profile_id
        for behaviour in scenario.behaviours
        if behaviour.source
        == SourceDomain.RESILIENCE
    }

    assert "failback_initiated" not in resilience_profiles
    assert "traffic_failback" not in resilience_profiles



def test_bank_06_state_sequence_is_runtime_legal() -> None:
    scenario = load_bank_06()

    machine = ScenarioStateMachine()

    assert (
        machine.state
        == scenario.state_sequence[0]
    )

    for state in scenario.state_sequence[1:]:
        machine.transition(state)

    assert (
        machine.state
        == scenario.state_sequence[-1]
    )
