from pathlib import Path

from pydantic import BaseModel, Field

from synthetic_ops_generator.config.loader import load_yaml_model
from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import Industry
from synthetic_ops_generator.topology.models import (
    Dependency,
    ServiceInstance,
    Site,
)
from synthetic_ops_generator.topology.validator import validate_topology


class BusinessStreamsConfig(BaseModel):
    business_streams: list[BusinessStream] = Field(default_factory=list)


class ServicesConfig(BaseModel):
    services: list[Service] = Field(default_factory=list)


class ComponentsConfig(BaseModel):
    components: list[Component] = Field(default_factory=list)


class SitesConfig(BaseModel):
    sites: list[Site] = Field(default_factory=list)
    service_instances: list[ServiceInstance] = Field(default_factory=list)


class TopologyConfig(BaseModel):
    dependencies: list[Dependency] = Field(default_factory=list)


class EnterpriseMeta(BaseModel):
    enterprise_id: str
    name: str
    industry: Industry


def load_enterprise_configuration(directory: str | Path) -> Enterprise:
    dir_path = Path(directory)

    meta_file = dir_path / "enterprise.yaml"
    meta = load_yaml_model(meta_file, EnterpriseMeta)

    streams_file = dir_path / "business_streams.yaml"
    streams_cfg = (
        load_yaml_model(streams_file, BusinessStreamsConfig)
        if streams_file.exists()
        else BusinessStreamsConfig()
    )

    services_file = dir_path / "services.yaml"
    services_cfg = (
        load_yaml_model(services_file, ServicesConfig)
        if services_file.exists()
        else ServicesConfig()
    )

    components_file = dir_path / "components.yaml"
    components_cfg = (
        load_yaml_model(components_file, ComponentsConfig)
        if components_file.exists()
        else ComponentsConfig()
    )

    sites_file = dir_path / "sites.yaml"
    sites_cfg = (
        load_yaml_model(sites_file, SitesConfig)
        if sites_file.exists()
        else SitesConfig()
    )

    topology_file = dir_path / "topology.yaml"
    topology_cfg = (
        load_yaml_model(topology_file, TopologyConfig)
        if topology_file.exists()
        else TopologyConfig()
    )

    enterprise = Enterprise(
        enterprise_id=meta.enterprise_id,
        name=meta.name,
        industry=meta.industry,
        business_streams=streams_cfg.business_streams,
        services=services_cfg.services,
        components=components_cfg.components,
        sites=sites_cfg.sites,
        service_instances=sites_cfg.service_instances,
        dependencies=topology_cfg.dependencies,
    )

    validate_topology(enterprise)
    return enterprise


load_enterprise = load_enterprise_configuration
