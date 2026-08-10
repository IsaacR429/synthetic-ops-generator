from pydantic import BaseModel, Field

from synthetic_ops_generator.domain.enums import (
    Criticality,
    Environment,
    Industry,
    WorkloadClass,
)


class BusinessStream(BaseModel):
    stream_id: str = Field(min_length=1)
    name: str = Field(min_length=1)


class Service(BaseModel):
    service_id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    business_stream_id: str = Field(min_length=1)

    owner: str = Field(min_length=1)
    criticality: Criticality

    workload_class: WorkloadClass | None = None

    benchmark_profile_id: str | None = None
    baseline_profile_id: str | None = None


class Component(BaseModel):
    component_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    component_type: str = Field(min_length=1)

    service_id: str = Field(min_length=1)
    environment: Environment


class Dependency(BaseModel):
    dependency_id: str = Field(min_length=1)

    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)

    relationship_type: str = Field(default="depends_on")
    criticality: Criticality


class Site(BaseModel):
    site_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    region: str = Field(min_length=1)
    role: str = Field(min_length=1)


class Enterprise(BaseModel):
    enterprise_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    industry: Industry

    business_streams: list[BusinessStream] = Field(default_factory=list)
    services: list[Service] = Field(default_factory=list)
    components: list[Component] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    sites: list[Site] = Field(default_factory=list)