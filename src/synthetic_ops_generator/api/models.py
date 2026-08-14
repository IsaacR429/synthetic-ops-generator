from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from synthetic_ops_generator.control.models import (
    ReplayExecutionResult,
    RunExecutionMode,
    RunRecord,
    RunStartResult,
    RunStatus,
    StopRunResult,
)
from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.domain.enums import (
    Action,
    Criticality,
    Decision,
    Environment,
    Industry,
    OperationalState,
    Outcome,
    RiskLevel,
    WorkloadClass,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
    ScenarioFamily,
    SourceDomain,
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str


class EnterpriseSummaryResponse(BaseModel):
    enterprise_id: str
    name: str
    industry: Industry

    business_stream_count: int = Field(ge=0)
    service_count: int = Field(ge=0)
    component_count: int = Field(ge=0)

    @classmethod
    def from_enterprise(
        cls,
        enterprise: Enterprise,
    ) -> "EnterpriseSummaryResponse":
        return cls(
            enterprise_id=(
                enterprise.enterprise_id
            ),
            name=enterprise.name,
            industry=enterprise.industry,
            business_stream_count=len(
                enterprise.business_streams
            ),
            service_count=len(
                enterprise.services
            ),
            component_count=len(
                enterprise.components
            ),
        )


class BusinessStreamResponse(BaseModel):
    stream_id: str
    name: str


class EnterpriseServiceResponse(BaseModel):
    service_id: str
    name: str

    business_stream_id: str

    owner: str
    criticality: Criticality

    workload_class: WorkloadClass | None = None

    benchmark_profile_id: str | None = None
    baseline_profile_id: str | None = None


class EnterpriseComponentResponse(BaseModel):
    component_id: str
    name: str
    component_type: str

    service_id: str
    environment: Environment


class EnterpriseDetailResponse(BaseModel):
    enterprise_id: str
    name: str
    industry: Industry

    business_streams: list[
        BusinessStreamResponse
    ] = Field(default_factory=list)

    services: list[
        EnterpriseServiceResponse
    ] = Field(default_factory=list)

    components: list[
        EnterpriseComponentResponse
    ] = Field(default_factory=list)

    @classmethod
    def from_enterprise(
        cls,
        enterprise: Enterprise,
    ) -> "EnterpriseDetailResponse":
        return cls.model_validate(
            enterprise.model_dump()
        )


class ScenarioSummaryResponse(BaseModel):
    scenario_id: str
    name: str
    description: str

    family: ScenarioFamily
    industry: Industry
    risk: RiskLevel

    enterprise_id: str
    environment: Environment

    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_definition(
        cls,
        scenario: ScenarioDefinition,
    ) -> "ScenarioSummaryResponse":
        return cls(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            description=scenario.description,
            family=scenario.family,
            industry=scenario.industry,
            risk=scenario.risk,
            enterprise_id=scenario.target.enterprise_id,
            environment=scenario.target.environment,
            tags=scenario.tags,
        )


class ScenarioTargetResponse(BaseModel):
    enterprise_id: str
    business_stream_id: str
    service_id: str

    component_ids: list[str] = Field(default_factory=list)

    environment: Environment


class ScenarioTriggerResponse(BaseModel):
    source: SourceDomain
    trigger_type: str
    description: str

    artifact: str | None = None
    version: str | None = None


class ScenarioBehaviourResponse(BaseModel):
    source: SourceDomain
    during_state: OperationalState
    profile_id: str

    description: str | None = None


class ExpectedScenarioResultResponse(BaseModel):
    scenario_id: str

    expected_decision: Decision | None = None
    expected_action: Action | None = None
    expected_outcome: Outcome

    expected_blocking_conditions: list[str] = Field(
        default_factory=list
    )
    expected_evidence: list[str] = Field(
        default_factory=list
    )

    expected_incident_attribution: bool | None = None

    expected_root_cause: str | None = None
    expected_insight: str | None = None


class ScenarioDetailResponse(BaseModel):
    scenario_id: str
    name: str
    description: str

    family: ScenarioFamily
    industry: Industry

    target: ScenarioTargetResponse

    risk: RiskLevel

    initial_conditions: list[str]

    trigger: ScenarioTriggerResponse

    state_sequence: list[OperationalState]

    behaviours: list[ScenarioBehaviourResponse]

    expected_result: ExpectedScenarioResultResponse

    assumptions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_definition(
        cls,
        scenario: ScenarioDefinition,
    ) -> "ScenarioDetailResponse":
        return cls.model_validate(
            scenario.model_dump()
        )


class StartRunRequest(BaseModel):
    scenario_id: str = Field(min_length=1)
    random_seed: int = 42
    execution_mode: RunExecutionMode = (
        RunExecutionMode.STANDARD
    )


class StartRunResponse(BaseModel):
    scenario_id: str
    run_id: str
    change_id: str
    status: RunStatus
    execution_mode: RunExecutionMode

    @classmethod
    def from_result(
        cls,
        result: RunStartResult,
    ) -> "StartRunResponse":
        return cls(
            scenario_id=result.scenario_id,
            run_id=result.run_id,
            change_id=result.change_id,
            status=result.status,
            execution_mode=result.execution_mode,
        )


class RunResponse(BaseModel):
    run_id: str
    scenario_id: str
    change_id: str

    status: RunStatus
    execution_mode: RunExecutionMode

    started_at: datetime
    completed_at: datetime | None

    current_state: OperationalState

    event_count: int = Field(ge=0)
    validation_passed: bool | None

    random_seed: int
    event_interval_seconds: float

    error_message: str | None = None

    @classmethod
    def from_record(
        cls,
        record: RunRecord,
    ) -> "RunResponse":
        return cls(
            run_id=record.run_id,
            scenario_id=record.scenario_id,
            change_id=record.change_id,
            status=record.status,
            execution_mode=record.execution_mode,
            started_at=record.started_at,
            completed_at=record.completed_at,
            current_state=record.current_state,
            event_count=record.event_count,
            validation_passed=(
                record.validation_passed
            ),
            random_seed=record.random_seed,
            event_interval_seconds=(
                record.event_interval_seconds
            ),
            error_message=record.error_message,
        )


class ReplayRunResponse(BaseModel):
    run_id: str
    scenario_id: str
    replayed_event_count: int = Field(ge=0)

    @classmethod
    def from_result(
        cls,
        result: ReplayExecutionResult,
    ) -> "ReplayRunResponse":
        return cls(
            run_id=result.run_id,
            scenario_id=result.scenario_id,
            replayed_event_count=(
                result.replayed_event_count
            ),
        )


class StopRunResponse(BaseModel):
    run_id: str
    scenario_id: str
    status: RunStatus
    event_count: int = Field(ge=0)

    @classmethod
    def from_result(
        cls,
        result: StopRunResult,
    ) -> "StopRunResponse":
        return cls(
            run_id=result.run_id,
            scenario_id=result.scenario_id,
            status=result.status,
            event_count=result.event_count,
        )