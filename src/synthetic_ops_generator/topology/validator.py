from synthetic_ops_generator.domain.enterprise import Enterprise


class TopologyValidationError(ValueError):
    pass


def validate_topology(enterprise: Enterprise) -> None:
    stream_ids = {s.stream_id for s in enterprise.business_streams}
    if len(stream_ids) != len(enterprise.business_streams):
        raise TopologyValidationError("Duplicate business stream IDs found.")

    service_ids = set()
    for service in enterprise.services:
        if service.service_id in service_ids:
            raise TopologyValidationError(
                f"Duplicate service ID: {service.service_id}"
            )
        service_ids.add(service.service_id)
        if service.business_stream_id not in stream_ids:
            raise TopologyValidationError(
                f"Service {service.service_id} references unknown business stream: {service.business_stream_id}"
            )

    component_ids = set()
    for component in enterprise.components:
        if component.component_id in component_ids:
            raise TopologyValidationError(
                f"Duplicate component ID: {component.component_id}"
            )
        component_ids.add(component.component_id)
        if component.service_id not in service_ids:
            raise TopologyValidationError(
                f"Component {component.component_id} references unknown service: {component.service_id}"
            )

    site_ids = set()
    for site in enterprise.sites:
        if site.site_id in site_ids:
            raise TopologyValidationError(
                f"Duplicate site ID: {site.site_id}"
            )
        site_ids.add(site.site_id)

    instance_ids = set()
    for instance in enterprise.service_instances:
        if instance.instance_id in instance_ids:
            raise TopologyValidationError(
                f"Duplicate service instance ID: {instance.instance_id}"
            )
        instance_ids.add(instance.instance_id)
        if instance.service_id not in service_ids:
            raise TopologyValidationError(
                f"Service instance {instance.instance_id} references unknown service: {instance.service_id}"
            )
        if instance.component_id and instance.component_id not in component_ids:
            raise TopologyValidationError(
                f"Service instance {instance.instance_id} references unknown component: {instance.component_id}"
            )
        if instance.site_id not in site_ids:
            raise TopologyValidationError(
                f"Service instance {instance.instance_id} references unknown site: {instance.site_id}"
            )

    valid_nodes = service_ids | component_ids
    dependency_ids = set()
    for dep in enterprise.dependencies:
        if dep.dependency_id in dependency_ids:
            raise TopologyValidationError(
                f"Duplicate dependency ID: {dep.dependency_id}"
            )
        dependency_ids.add(dep.dependency_id)
        if dep.source_id not in valid_nodes:
            raise TopologyValidationError(
                f"Dependency {dep.dependency_id} source {dep.source_id} not found in services or components."
            )
        if dep.target_id not in valid_nodes:
            raise TopologyValidationError(
                f"Dependency {dep.dependency_id} target {dep.target_id} not found in services or components."
            )
