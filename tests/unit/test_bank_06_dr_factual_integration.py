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


def load_bank_06():
    return load_scenario(
        "config/scenarios/banking/BANK-06.yaml"
    )


def load_bank_alpha():
    return load_enterprise(
        "config/enterprises/bank_alpha"
    )


def resilience_by_profile():
    scenario = load_bank_06()

    return {
        behaviour.profile_id: behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.RESILIENCE
    }


def test_bank_06_explicitly_observes_primary_unavailability() -> None:
    behaviours = resilience_by_profile()

    behaviour = behaviours["service_unavailable"]

    assert (
        behaviour.during_state
        == OperationalState.FAILURE
    )
    assert (
        behaviour.execution_node_id
        == "payment_api_primary"
    )
    assert behaviour.continuous is False
    assert behaviour.resilience_transition is None
    assert behaviour.resilience_replication is None


def test_bank_06_records_primary_to_secondary_replication_fact() -> None:
    behaviours = resilience_by_profile()

    behaviour = behaviours["replication_observed"]

    assert (
        behaviour.during_state
        == OperationalState.FAILURE
    )
    assert (
        behaviour.execution_node_id
        == "payment_api_primary"
    )
    assert behaviour.continuous is False

    assert behaviour.resilience_transition is None
    assert behaviour.resilience_replication is not None

    replication = behaviour.resilience_replication

    assert (
        replication.to_execution_node_id
        == "payment_api_secondary"
    )
    assert (
        replication.replication_status
        == ReplicationStatus.STOPPED
    )
    assert (
        replication
        .last_successful_replication_offset_seconds
        == 60.0
    )


def test_bank_06_explicitly_observes_secondary_availability() -> None:
    behaviours = resilience_by_profile()

    behaviour = behaviours["service_available"]

    secondary_available = [
        candidate
        for candidate in load_bank_06().behaviours
        if (
            candidate.source == SourceDomain.RESILIENCE
            and candidate.profile_id == "service_available"
            and candidate.execution_node_id
            == "payment_api_secondary"
        )
    ]

    assert len(secondary_available) == 1

    behaviour = secondary_available[0]

    assert (
        behaviour.during_state
        == OperationalState.REMEDIATION
    )
    assert behaviour.continuous is False
    assert behaviour.resilience_transition is None
    assert behaviour.resilience_replication is None


def test_bank_06_explicitly_observes_primary_recovery_availability() -> None:
    primary_available = [
        behaviour
        for behaviour in load_bank_06().behaviours
        if (
            behaviour.source == SourceDomain.RESILIENCE
            and behaviour.profile_id == "service_available"
            and behaviour.execution_node_id
            == "payment_api_primary"
        )
    ]

    assert len(primary_available) == 1

    behaviour = primary_available[0]

    assert (
        behaviour.during_state
        == OperationalState.RECOVERY
    )
    assert behaviour.continuous is False
    assert behaviour.resilience_transition is None
    assert behaviour.resilience_replication is None


def test_bank_06_plan_resolves_replication_peer_independently_of_failover_peer() -> None:
    scenario = load_bank_06()
    enterprise = load_bank_alpha()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    replication_entries = [
        entry
        for entry in plan.entries
        if (
            entry.behaviour.source
            == SourceDomain.RESILIENCE
            and entry.behaviour.profile_id
            == "replication_observed"
        )
    ]

    assert len(replication_entries) == 1

    entry = replication_entries[0]

    assert entry.execution_target is not None
    assert (
        entry.execution_target.service_instance_id
        == "payment_api_primary"
    )
    assert (
        entry.execution_target.site_id
        == "bank_primary"
    )

    assert entry.resilience_transition_target is None
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


def test_bank_06_expected_evidence_names_new_factual_dr_observations() -> None:
    scenario = load_bank_06()

    expected = set(
        scenario.expected_result.expected_evidence
    )

    assert {
        "primary_payment_api_unavailable",
        "primary_to_secondary_replication_stopped",
        "secondary_payment_api_available",
        "primary_payment_api_available_after_recovery",
    } <= expected
