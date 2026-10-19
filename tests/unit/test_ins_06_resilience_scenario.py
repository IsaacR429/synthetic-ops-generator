from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
    SourceDomain,
)
from synthetic_ops_generator.domain.resilience import (
    ReplicationStatus,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.state_machine import (
    ScenarioStateMachine,
)


def load_insurer_alpha():
    return load_enterprise(
        "config/enterprises/insurer_alpha"
    )


def load_ins_06():
    return load_scenario(
        "config/scenarios/insurance/INS-06.yaml"
    )


def test_ins_06_targets_claims_dr_topology() -> None:
    scenario = load_ins_06()

    assert scenario.scenario_id == "INS-06"
    assert scenario.industry.value == "insurance"

    assert (
        scenario.target.enterprise_id
        == "insurer_alpha"
    )
    assert (
        scenario.target.business_stream_id
        == "claims"
    )
    assert (
        scenario.target.service_id
        == "claims_service"
    )

    assert "claims_api" in scenario.target.component_ids

    assert scenario.correlation.change_required is False


def test_ins_06_defines_complete_factual_claims_failover() -> None:
    scenario = load_ins_06()

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


def test_ins_06_primary_unavailability_is_explicit_fact() -> None:
    scenario = load_ins_06()

    behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.source == SourceDomain.RESILIENCE
            and behaviour.profile_id
            == "service_unavailable"
        )
    ]

    assert len(behaviours) == 1

    behaviour = behaviours[0]

    assert (
        behaviour.execution_node_id
        == "claims_api_primary"
    )
    assert (
        behaviour.during_state
        == OperationalState.FAILURE
    )
    assert behaviour.continuous is False
    assert behaviour.resilience_transition is None
    assert behaviour.resilience_replication is None


def test_ins_06_records_claims_replication_lag() -> None:
    scenario = load_ins_06()

    behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.source == SourceDomain.RESILIENCE
            and behaviour.profile_id
            == "replication_observed"
        )
    ]

    assert len(behaviours) == 1

    behaviour = behaviours[0]

    assert (
        behaviour.execution_node_id
        == "claims_api_primary"
    )
    assert (
        behaviour.during_state
        == OperationalState.FAILURE
    )
    assert behaviour.continuous is False

    assert behaviour.resilience_transition is None
    assert behaviour.resilience_replication is not None

    replication = behaviour.resilience_replication

    assert (
        replication.to_execution_node_id
        == "claims_api_secondary"
    )
    assert (
        replication.replication_status
        == ReplicationStatus.LAGGING
    )
    assert (
        replication
        .last_successful_replication_offset_seconds
        == 120.0
    )


def test_ins_06_failover_transitions_primary_to_secondary() -> None:
    scenario = load_ins_06()

    transition_behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.source == SourceDomain.RESILIENCE
            and behaviour.resilience_transition
            is not None
        )
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
            == "claims_api_primary"
        )
        assert (
            behaviour.resilience_transition
            .to_execution_node_id
            == "claims_api_secondary"
        )


def test_ins_06_secondary_activation_availability_and_serving_are_distinct() -> None:
    scenario = load_ins_06()

    secondary_profiles = [
        behaviour.profile_id
        for behaviour in scenario.behaviours
        if (
            behaviour.source == SourceDomain.RESILIENCE
            and behaviour.execution_node_id
            == "claims_api_secondary"
        )
    ]

    assert secondary_profiles == [
        "instance_activated",
        "service_available",
        "instance_serving",
    ]


def test_ins_06_primary_recovery_does_not_model_failback() -> None:
    scenario = load_ins_06()

    primary_recovery = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.execution_node_id
            == "claims_api_primary"
            and behaviour.during_state
            == OperationalState.RECOVERY
        )
    ]

    assert {
        behaviour.profile_id
        for behaviour in primary_recovery
    } >= {
        "service_available",
        "all_required_checks_pass",
        "operational_recovery",
    }

    resilience_profiles = {
        behaviour.profile_id
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.RESILIENCE
    }

    assert "failback_initiated" not in resilience_profiles
    assert "traffic_failback" not in resilience_profiles


def test_ins_06_resilience_facts_are_bounded() -> None:
    scenario = load_ins_06()

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


def test_ins_06_secondary_recovery_telemetry_is_continuous() -> None:
    scenario = load_ins_06()

    secondary_continuous = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.continuous
            and behaviour.execution_node_id
            == "claims_api_secondary"
        )
    ]

    assert secondary_continuous

    assert {
        behaviour.source
        for behaviour in secondary_continuous
    } == {
        SourceDomain.METRIC,
        SourceDomain.LOG,
    }


def test_ins_06_plan_resolves_claims_replication_and_failover_peers() -> None:
    scenario = load_ins_06()
    enterprise = load_insurer_alpha()

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
        if entry.resilience_transition_target
        is not None
    ]

    assert len(transition_entries) == 3

    for entry in transition_entries:
        assert (
            entry.execution_target
            .service_instance_id
            == "claims_api_primary"
        )
        assert (
            entry.execution_target.site_id
            == "insurer_primary"
        )
        assert (
            entry.resilience_transition_target
            .service_instance_id
            == "claims_api_secondary"
        )
        assert (
            entry.resilience_transition_target.site_id
            == "insurer_secondary"
        )

    replication_entries = [
        entry
        for entry in resilience_entries
        if entry.resilience_replication_target
        is not None
    ]

    assert len(replication_entries) == 1

    entry = replication_entries[0]

    assert (
        entry.execution_target.service_instance_id
        == "claims_api_primary"
    )
    assert (
        entry.execution_target.site_id
        == "insurer_primary"
    )

    assert entry.resilience_transition_target is None

    assert (
        entry.resilience_replication_target
        .service_instance_id
        == "claims_api_secondary"
    )
    assert (
        entry.resilience_replication_target.site_id
        == "insurer_secondary"
    )


def test_ins_06_expected_evidence_is_claims_specific() -> None:
    scenario = load_ins_06()

    expected = set(
        scenario.expected_result.expected_evidence
    )

    assert {
        "primary_claims_api_unavailable",
        "primary_to_secondary_claims_replication_lag",
        "claims_failover_initiated",
        "claims_traffic_switch_completed",
        "secondary_claims_api_available",
        "secondary_claims_api_serving",
        "claims_intake_restored",
        "primary_claims_api_available_after_recovery",
    } <= expected


def test_ins_06_does_not_encode_rto_rpo_or_dr_success_as_source_behaviour() -> None:
    scenario = load_ins_06()

    forbidden_profiles = {
        "rto_met",
        "rto_breached",
        "rpo_met",
        "rpo_breached",
        "data_loss",
        "dr_success",
        "recovery_success",
    }

    assert forbidden_profiles.isdisjoint(
        {
            behaviour.profile_id
            for behaviour in scenario.behaviours
        }
    )

    for behaviour in scenario.behaviours:
        dumped = behaviour.model_dump()

        assert "rto_met" not in dumped
        assert "rpo_met" not in dumped
        assert "data_loss" not in dumped
        assert "dr_success" not in dumped


def test_ins_06_state_sequence_is_runtime_legal() -> None:
    scenario = load_ins_06()

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
