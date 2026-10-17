from __future__ import annotations

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.checks.applicability import (
    is_check_applicable,
)
from synthetic_ops_generator.checks.models import (
    CheckApplicability,
    CheckDefinition,
)
from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.domain.enums import (
    AssetClass,
    MissionCriticality,
    ServiceClass,
)
from synthetic_ops_generator.domain.operational_test import (
    TestCategory as Category,
)
from synthetic_ops_generator.topology.resolver import (
    TopologyResolver,
)


def _insurer_topology() -> TopologyResolver:
    enterprise = load_enterprise_configuration(
        "config/enterprises/insurer_alpha"
    )

    return TopologyResolver(
        enterprise
    )


def test_check_definition_preserves_reusable_identity() -> None:
    definition = CheckDefinition(
        check_definition_id="database_connectivity",
        category=Category.INFRASTRUCTURE,
        test_type="connectivity",
        name="Database connectivity",
        description=(
            "Validate connectivity to a database asset."
        ),
        applicability=CheckApplicability(
            asset_classes={
                AssetClass.DATABASE,
            },
        ),
    )

    assert (
        definition.check_definition_id
        == "database_connectivity"
    )
    assert (
        definition.category
        == Category.INFRASTRUCTURE
    )
    assert definition.test_type == "connectivity"
    assert definition.name == "Database connectivity"

    assert definition.applicability.asset_classes == {
        AssetClass.DATABASE,
    }


def test_check_definition_rejects_invalid_category() -> None:
    with pytest.raises(ValidationError):
        CheckDefinition(
            check_definition_id="invalid",
            category="made_up_category",
            test_type="invalid",
            name="Invalid",
            applicability=CheckApplicability(),
        )


def test_check_definition_does_not_own_execution_or_schedule_state() -> None:
    fields = set(
        CheckDefinition.model_fields
    )

    forbidden = {
        "test_id",
        "chg_id",
        "mandatory",
        "status",
        "result",
        "planned_at",
        "executed_at",
        "failure_reason",
        "profile_id",
        "during_state",
        "continuous",
        "schedule",
        "interval_seconds",
        "warning_threshold",
        "blocking_threshold",
    }

    assert fields.isdisjoint(
        forbidden
    )


def test_database_check_applies_to_existing_business_database() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="database_connectivity",
        category=Category.INFRASTRUCTURE,
        test_type="connectivity",
        name="Database connectivity",
        applicability=CheckApplicability(
            asset_classes={
                AssetClass.DATABASE,
            },
        ),
    )

    claims_database = topology.resolve_node(
        "claims_database"
    )

    claims_api = topology.resolve_node(
        "claims_api"
    )

    assert is_check_applicable(
        definition,
        claims_database,
    )

    assert not is_check_applicable(
        definition,
        claims_api,
    )


def test_database_check_applies_to_shared_database_platform() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="database_connectivity",
        category=Category.INFRASTRUCTURE,
        test_type="connectivity",
        name="Database connectivity",
        applicability=CheckApplicability(
            asset_classes={
                AssetClass.DATABASE,
            },
        ),
    )

    shared_database = topology.resolve_node(
        "insurer_shared_database"
    )

    assert is_check_applicable(
        definition,
        shared_database,
    )


def test_network_check_targets_network_assets_only() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="network_connectivity",
        category=Category.INFRASTRUCTURE,
        test_type="connectivity",
        name="Network connectivity",
        applicability=CheckApplicability(
            asset_classes={
                AssetClass.NETWORK,
            },
        ),
    )

    network = topology.resolve_node(
        "insurer_core_network"
    )

    middleware = topology.resolve_node(
        "insurer_message_broker"
    )

    assert is_check_applicable(
        definition,
        network,
    )

    assert not is_check_applicable(
        definition,
        middleware,
    )


def test_application_check_uses_service_classification() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="application_smoke",
        category=Category.APPLICATION,
        test_type="post_deployment_smoke",
        name="Application smoke validation",
        applicability=CheckApplicability(
            service_classes={
                ServiceClass.BUSINESS_APPLICATION,
            },
        ),
    )

    claims = topology.resolve_node(
        "claims_service"
    )

    network = topology.resolve_node(
        "insurer_network_service"
    )

    assert is_check_applicable(
        definition,
        claims,
    )

    assert not is_check_applicable(
        definition,
        network,
    )


def test_applicability_dimensions_are_combined_with_and_semantics() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="mission_critical_application_smoke",
        category=Category.APPLICATION,
        test_type="post_deployment_smoke",
        name="Mission-critical application smoke",
        applicability=CheckApplicability(
            service_classes={
                ServiceClass.BUSINESS_APPLICATION,
            },
            mission_criticalities={
                MissionCriticality.MISSION_CRITICAL,
            },
        ),
    )

    claims = topology.resolve_node(
        "claims_service"
    )

    broker = topology.resolve_node(
        "broker_portal"
    )

    assert (
        claims.service_class
        == ServiceClass.BUSINESS_APPLICATION
    )
    assert (
        claims.mission_criticality
        == MissionCriticality.MISSION_CRITICAL
    )

    assert (
        broker.service_class
        == ServiceClass.BUSINESS_APPLICATION
    )
    assert (
        broker.mission_criticality
        == MissionCriticality.NON_MISSION_CRITICAL
    )

    assert is_check_applicable(
        definition,
        claims,
    )

    assert not is_check_applicable(
        definition,
        broker,
    )


def test_values_inside_one_dimension_use_or_semantics() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="business_service_validation",
        category=Category.APPLICATION,
        test_type="functional_validation",
        name="Business service validation",
        applicability=CheckApplicability(
            service_classes={
                ServiceClass.BUSINESS_APPLICATION,
                ServiceClass.BUSINESS_SERVICE,
            },
        ),
    )

    claims = topology.resolve_node(
        "claims_service"
    )

    claims_payment = topology.resolve_node(
        "claims_payment_service"
    )

    network = topology.resolve_node(
        "insurer_network_service"
    )

    assert is_check_applicable(
        definition,
        claims,
    )

    assert is_check_applicable(
        definition,
        claims_payment,
    )

    assert not is_check_applicable(
        definition,
        network,
    )


def test_unconstrained_applicability_matches_any_resolved_node() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="generic_validation",
        category=Category.INFRASTRUCTURE,
        test_type="generic_validation",
        name="Generic validation",
        applicability=CheckApplicability(),
    )

    assert is_check_applicable(
        definition,
        topology.resolve_node(
            "claims_service"
        ),
    )

    assert is_check_applicable(
        definition,
        topology.resolve_node(
            "insurer_core_network"
        ),
    )


def test_service_instance_uses_inherited_semantic_context() -> None:
    topology = _insurer_topology()

    definition = CheckDefinition(
        check_definition_id="application_instance_validation",
        category=Category.APPLICATION,
        test_type="instance_validation",
        name="Application instance validation",
        applicability=CheckApplicability(
            service_classes={
                ServiceClass.BUSINESS_APPLICATION,
            },
            asset_classes={
                AssetClass.APPLICATION,
            },
        ),
    )

    instance = topology.resolve_execution_node(
        "claims_api_primary"
    )

    assert instance.node_type == "service_instance"
    assert (
        instance.service_class
        == ServiceClass.BUSINESS_APPLICATION
    )
    assert (
        instance.asset_class
        == AssetClass.APPLICATION
    )

    assert is_check_applicable(
        definition,
        instance,
    )
