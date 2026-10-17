from __future__ import annotations

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import (
    Criticality,
    Environment,
    Industry,
)
from synthetic_ops_generator.topology.models import (
    ServiceInstance,
    Site,
    SiteRole,
)
from synthetic_ops_generator.topology.resolver import (
    TopologyResolver,
)


def _service(
    **overrides,
) -> Service:
    values = {
        "service_id": "claims_service",
        "name": "Claims Processing",
        "business_stream_id": "claims",
        "owner": "claims_operations",
        "criticality": Criticality.HIGH,
        "workload_class": "business_workflow",
        "service_class": "business_application",
        "mission_criticality": "mission_critical",
    }
    values.update(overrides)
    return Service(**values)


def _component(
    **overrides,
) -> Component:
    values = {
        "component_id": "claims_database",
        "name": "Claims Database",
        "component_type": "database",
        "asset_class": "database",
        "service_id": "claims_service",
        "environment": Environment.PRODUCTION,
    }
    values.update(overrides)
    return Component(**values)


def _enterprise(
    *,
    service: Service | None = None,
    component: Component | None = None,
    with_instance: bool = False,
) -> Enterprise:
    service = service or _service()
    component = component or _component()

    sites = []
    instances = []

    if with_instance:
        sites = [
            Site(
                site_id="insurer_primary",
                name="Insurer Primary",
                region="region_a",
                role=SiteRole.PRIMARY,
            )
        ]

        instances = [
            ServiceInstance(
                instance_id="claims_database_primary",
                service_id=service.service_id,
                component_id=component.component_id,
                site_id="insurer_primary",
                environment=Environment.PRODUCTION,
            )
        ]

    return Enterprise(
        enterprise_id="insurer_alpha",
        name="Insurer Alpha",
        industry=Industry.INSURANCE,
        business_streams=[
            BusinessStream(
                stream_id="claims",
                name="Claims",
            )
        ],
        services=[service],
        components=[component],
        sites=sites,
        service_instances=instances,
    )


def test_service_preserves_enterprise_assurance_semantics() -> None:
    service = _service()

    assert service.service_class == "business_application"
    assert service.mission_criticality == "mission_critical"

    # Existing operational criticality remains independent.
    assert service.criticality == Criticality.HIGH


def test_component_preserves_assurance_asset_class() -> None:
    component = _component()

    assert component.component_type == "database"
    assert component.asset_class == "database"


def test_service_rejects_unknown_service_class() -> None:
    with pytest.raises(ValidationError):
        _service(
            service_class="made_up_service_class",
        )


def test_service_rejects_unknown_mission_criticality() -> None:
    with pytest.raises(ValidationError):
        _service(
            mission_criticality="super_critical",
        )


def test_component_rejects_unknown_asset_class() -> None:
    with pytest.raises(ValidationError):
        _component(
            asset_class="unknown_asset_class",
        )


def test_new_assurance_fields_remain_backward_compatible() -> None:
    service = Service(
        service_id="legacy_service",
        name="Legacy Service",
        business_stream_id="claims",
        owner="legacy_operations",
        criticality=Criticality.MEDIUM,
    )

    component = Component(
        component_id="legacy_component",
        name="Legacy Component",
        component_type="worker",
        service_id="legacy_service",
        environment=Environment.PRODUCTION,
    )

    assert service.service_class is None
    assert service.mission_criticality is None
    assert component.asset_class is None


def test_topology_resolution_projects_service_assurance_context() -> None:
    enterprise = _enterprise()

    resolver = TopologyResolver(
        enterprise,
    )

    node = resolver.resolve_node(
        "claims_service"
    )

    assert node.service_class == "business_application"
    assert node.service_owner == "claims_operations"
    assert node.service_criticality == Criticality.HIGH
    assert node.mission_criticality == "mission_critical"

    assert node.component_type is None
    assert node.asset_class is None


def test_component_resolution_inherits_service_assurance_context() -> None:
    enterprise = _enterprise()

    resolver = TopologyResolver(
        enterprise,
    )

    node = resolver.resolve_node(
        "claims_database"
    )

    assert node.service_class == "business_application"
    assert node.service_owner == "claims_operations"
    assert node.service_criticality == Criticality.HIGH
    assert node.mission_criticality == "mission_critical"

    assert node.component_type == "database"
    assert node.asset_class == "database"


def test_service_instance_resolution_inherits_parent_assurance_context() -> None:
    enterprise = _enterprise(
        with_instance=True,
    )

    resolver = TopologyResolver(
        enterprise,
    )

    node = resolver.resolve_execution_node(
        "claims_database_primary"
    )

    assert node.node_type == "service_instance"

    assert node.service_class == "business_application"
    assert node.service_owner == "claims_operations"
    assert node.service_criticality == Criticality.HIGH
    assert node.mission_criticality == "mission_critical"

    assert node.component_type == "database"
    assert node.asset_class == "database"

    assert node.site_id == "insurer_primary"
    assert (
        node.service_instance_id
        == "claims_database_primary"
    )
