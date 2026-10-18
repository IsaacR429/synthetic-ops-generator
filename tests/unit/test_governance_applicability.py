from __future__ import annotations

from synthetic_ops_generator.domain.enums import (
    AssetClass,
    Environment,
    MissionCriticality,
    RiskLevel,
    ServiceClass,
)
from synthetic_ops_generator.governance.applicability import (
    ApplicabilityDimensionStatus,
    ControlApplicabilityStatus,
    PolicyApplicabilityContext,
    resolve_control_applicability,
)
from synthetic_ops_generator.governance.models import (
    PolicyApplicability,
    PolicyControl,
)
from synthetic_ops_generator.topology.resolver import (
    ResolvedTopologyNode,
)


def _control(
    applicability: PolicyApplicability | None = None,
) -> PolicyControl:
    return PolicyControl(
        control_id="CTRL-P3B-001",
        policy_id="POL-P3B-001",
        control_reference="4.2.3",
        title="Production validation",
        objective=(
            "Require validation for applicable enterprise targets."
        ),
        applicability=(
            applicability
            if applicability is not None
            else PolicyApplicability()
        ),
        requirement_ids=(
            "REQ-P3B-001",
        ),
    )


def _component_target(
    *,
    service_class: ServiceClass | None = (
        ServiceClass.BUSINESS_APPLICATION
    ),
    mission_criticality: MissionCriticality | None = (
        MissionCriticality.MISSION_CRITICAL
    ),
    asset_class: AssetClass | None = AssetClass.APPLICATION,
    environment: Environment | None = Environment.PRODUCTION,
) -> ResolvedTopologyNode:
    return ResolvedTopologyNode(
        node_id="claims-api",
        node_type="component",
        service_id="claims-service",
        business_stream_id="claims",
        service_class=service_class,
        service_owner="Claims Platform",
        mission_criticality=mission_criticality,
        component_type="api",
        asset_class=asset_class,
        component_id="claims-api",
        environment=environment,
    )


def _service_target(
    *,
    service_class: ServiceClass | None = (
        ServiceClass.BUSINESS_APPLICATION
    ),
    mission_criticality: MissionCriticality | None = (
        MissionCriticality.MISSION_CRITICAL
    ),
) -> ResolvedTopologyNode:
    return ResolvedTopologyNode(
        node_id="claims-service",
        node_type="service",
        service_id="claims-service",
        business_stream_id="claims",
        service_class=service_class,
        service_owner="Claims Platform",
        mission_criticality=mission_criticality,
    )


def _applicability() -> PolicyApplicability:
    return PolicyApplicability(
        environments={
            Environment.PRODUCTION,
        },
        service_classes={
            ServiceClass.BUSINESS_APPLICATION,
        },
        mission_criticalities={
            MissionCriticality.MISSION_CRITICAL,
        },
        asset_classes={
            AssetClass.APPLICATION,
        },
        change_risks={
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        },
    )


def test_unconstrained_control_is_applicable() -> None:
    result = resolve_control_applicability(
        control=_control(),
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_all_populated_dimensions_matching_is_applicable() -> None:
    result = resolve_control_applicability(
        control=_control(_applicability()),
        context=PolicyApplicabilityContext(
            target=_component_target(),
            environment=Environment.PRODUCTION,
            change_risk=RiskLevel.HIGH,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_values_inside_one_dimension_use_or_semantics() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                change_risks={
                    RiskLevel.HIGH,
                    RiskLevel.CRITICAL,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_service_target(),
            change_risk=RiskLevel.CRITICAL,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_environment_mismatch_is_not_applicable() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                environment=Environment.STAGING,
            ),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.NOT_APPLICABLE
    )


def test_service_class_mismatch_is_not_applicable() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                service_classes={
                    ServiceClass.BUSINESS_APPLICATION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                service_class=(
                    ServiceClass.INFRASTRUCTURE_SERVICE
                ),
            ),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.NOT_APPLICABLE
    )


def test_missing_mission_criticality_is_indeterminate() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                mission_criticalities={
                    MissionCriticality.MISSION_CRITICAL,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_service_target(
                mission_criticality=None,
            ),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )


def test_missing_asset_class_is_indeterminate_when_constrained() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                asset_classes={
                    AssetClass.APPLICATION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )


def test_missing_change_risk_is_indeterminate_when_constrained() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                change_risks={
                    RiskLevel.HIGH,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )


def test_missing_environment_is_indeterminate_when_constrained() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )


def test_explicit_environment_supplies_service_level_context() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
                service_classes={
                    ServiceClass.BUSINESS_APPLICATION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_service_target(),
            environment=Environment.PRODUCTION,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_topology_environment_is_used_when_context_omits_it() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                environment=Environment.PRODUCTION,
            ),
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_conflicting_environment_sources_are_indeterminate() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                environment=Environment.PRODUCTION,
            ),
            environment=Environment.STAGING,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )

    assert (
        result.evaluated_dimensions["environment"]
        == ApplicabilityDimensionStatus.UNKNOWN
    )


def test_known_mismatch_outweighs_unrelated_unknown_context() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
                change_risks={
                    RiskLevel.HIGH,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                environment=Environment.STAGING,
            ),
            change_risk=None,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.NOT_APPLICABLE
    )


def test_unknown_without_any_mismatch_is_indeterminate() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
                change_risks={
                    RiskLevel.HIGH,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                environment=Environment.PRODUCTION,
            ),
            change_risk=None,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )


def test_dimension_results_explain_resolution() -> None:
    result = resolve_control_applicability(
        control=_control(_applicability()),
        context=PolicyApplicabilityContext(
            target=_component_target(),
            environment=Environment.PRODUCTION,
            change_risk=RiskLevel.HIGH,
        ),
    )

    assert result.evaluated_dimensions == {
        "environment": ApplicabilityDimensionStatus.MATCH,
        "service_class": ApplicabilityDimensionStatus.MATCH,
        "mission_criticality": (
            ApplicabilityDimensionStatus.MATCH
        ),
        "asset_class": ApplicabilityDimensionStatus.MATCH,
        "change_risk": ApplicabilityDimensionStatus.MATCH,
    }


def test_empty_selector_dimensions_are_reported_unconstrained() -> None:
    result = resolve_control_applicability(
        control=_control(),
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    assert result.evaluated_dimensions == {
        "environment": (
            ApplicabilityDimensionStatus.UNCONSTRAINED
        ),
        "service_class": (
            ApplicabilityDimensionStatus.UNCONSTRAINED
        ),
        "mission_criticality": (
            ApplicabilityDimensionStatus.UNCONSTRAINED
        ),
        "asset_class": (
            ApplicabilityDimensionStatus.UNCONSTRAINED
        ),
        "change_risk": (
            ApplicabilityDimensionStatus.UNCONSTRAINED
        ),
    }


def test_result_preserves_control_identity() -> None:
    control = _control()

    result = resolve_control_applicability(
        control=control,
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    assert result.control_id == control.control_id


def test_applicability_resolution_does_not_make_runtime_decisions() -> None:
    result = resolve_control_applicability(
        control=_control(),
        context=PolicyApplicabilityContext(
            target=_service_target(),
        ),
    )

    fields = result.model_fields

    assert "blocking" not in fields
    assert "decision" not in fields
    assert "action" not in fields
    assert "outcome" not in fields
    assert "waived" not in fields

def test_service_instance_target_uses_inherited_enterprise_semantics() -> None:
    target = ResolvedTopologyNode(
        node_id="claims-primary",
        node_type="service_instance",
        service_id="claims-service",
        business_stream_id="claims",
        service_class=ServiceClass.BUSINESS_APPLICATION,
        service_owner="Claims Platform",
        mission_criticality=(
            MissionCriticality.MISSION_CRITICAL
        ),
        component_type="api",
        asset_class=AssetClass.APPLICATION,
        component_id="claims-api",
        environment=Environment.PRODUCTION,
        site_id="primary-site",
        service_instance_id="claims-primary",
    )

    result = resolve_control_applicability(
        control=_control(_applicability()),
        context=PolicyApplicabilityContext(
            target=target,
            change_risk=RiskLevel.HIGH,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )


def test_service_instance_without_asset_context_is_indeterminate() -> None:
    target = ResolvedTopologyNode(
        node_id="claims-primary",
        node_type="service_instance",
        service_id="claims-service",
        business_stream_id="claims",
        service_class=ServiceClass.BUSINESS_APPLICATION,
        service_owner="Claims Platform",
        mission_criticality=(
            MissionCriticality.MISSION_CRITICAL
        ),
        component_id=None,
        asset_class=None,
        environment=Environment.PRODUCTION,
        site_id="primary-site",
        service_instance_id="claims-primary",
    )

    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                asset_classes={
                    AssetClass.APPLICATION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=target,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.INDETERMINATE
    )

    assert (
        result.evaluated_dimensions["asset_class"]
        == ApplicabilityDimensionStatus.UNKNOWN
    )


def test_equal_explicit_and_topology_environment_is_match() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                environment=Environment.PRODUCTION,
            ),
            environment=Environment.PRODUCTION,
        ),
    )

    assert (
        result.status
        == ControlApplicabilityStatus.APPLICABLE
    )

    assert (
        result.evaluated_dimensions["environment"]
        == ApplicabilityDimensionStatus.MATCH
    )


def test_definitive_mismatch_outweighs_environment_conflict() -> None:
    result = resolve_control_applicability(
        control=_control(
            PolicyApplicability(
                environments={
                    Environment.PRODUCTION,
                },
                service_classes={
                    ServiceClass.BUSINESS_APPLICATION,
                },
            )
        ),
        context=PolicyApplicabilityContext(
            target=_component_target(
                service_class=(
                    ServiceClass.INFRASTRUCTURE_SERVICE
                ),
                environment=Environment.PRODUCTION,
            ),
            environment=Environment.STAGING,
        ),
    )

    assert (
        result.evaluated_dimensions["environment"]
        == ApplicabilityDimensionStatus.UNKNOWN
    )

    assert (
        result.evaluated_dimensions["service_class"]
        == ApplicabilityDimensionStatus.MISMATCH
    )

    assert (
        result.status
        == ControlApplicabilityStatus.NOT_APPLICABLE
    )


def test_applicability_context_does_not_embed_change_lifecycle() -> None:
    fields = PolicyApplicabilityContext.model_fields

    assert "change_risk" in fields

    assert "change" not in fields
    assert "chg_id" not in fields
    assert "change_status" not in fields
    assert "approvals" not in fields

