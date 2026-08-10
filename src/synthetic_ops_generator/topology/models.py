from enum import StrEnum

from pydantic import BaseModel, Field

from synthetic_ops_generator.domain.enums import (
    Criticality,
    Environment,
)


class DependencyRelationship(StrEnum):
    DEPENDS_ON = "depends_on"
    RUNS_ON = "runs_on"
    CALLS = "calls"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"


class SiteRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    ACTIVE = "active"
    STANDBY = "standby"


class Dependency(BaseModel):
    dependency_id: str = Field(min_length=1)

    source_id: str = Field(min_length=1)
    target_id: str = Field(min_length=1)

    relationship_type: DependencyRelationship
    criticality: Criticality


class Site(BaseModel):
    site_id: str = Field(min_length=1)
    name: str = Field(min_length=1)

    region: str = Field(min_length=1)
    role: SiteRole


class ServiceInstance(BaseModel):
    instance_id: str = Field(min_length=1)

    service_id: str = Field(min_length=1)
    component_id: str | None = None

    site_id: str = Field(min_length=1)

    environment: Environment
