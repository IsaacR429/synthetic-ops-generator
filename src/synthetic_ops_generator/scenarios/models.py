from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from synthetic_ops_generator.domain.enums import (
    Environment,
    Industry,
    OperationalState,
    RiskLevel,
)
from synthetic_ops_generator.oracle.models import ExpectedScenarioResult


class ScenarioFamily(StrEnum):
    CHANGE_VALIDATION = "change_validation"
    OPERATIONAL_DEGRADATION = "operational_degradation"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"
    RESILIENCE_DR = "resilience_dr"
    GOVERNANCE_AUDIT = "governance_audit"
    PREDICTIVE_INTELLIGENCE = "predictive_intelligence"
    EXECUTIVE_INTELLIGENCE = "executive_intelligence"


class SourceDomain(StrEnum):
    ITSM = "itsm"
    DEPLOYMENT = "deployment"
    APPLICATION_TEST = "application_test"
    INFRASTRUCTURE_TEST = "infrastructure_test"
    METRIC = "metric"
    LOG = "log"
    MANUAL_VALIDATION = "manual_validation"
    INCIDENT = "incident"
    EVIDENCE = "evidence"


class ScenarioTarget(BaseModel):
    enterprise_id: str = Field(min_length=1)
    business_stream_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)

    component_ids: list[str] = Field(
        default_factory=list
    )

    environment: Environment


class ScenarioTrigger(BaseModel):
    source: SourceDomain

    trigger_type: str = Field(min_length=1)
    description: str = Field(min_length=1)

    artifact: str | None = None
    version: str | None = None


class ScenarioBehaviour(BaseModel):
    source: SourceDomain

    during_state: OperationalState

    profile_id: str = Field(min_length=1)

    description: str | None = None

    continuous: bool = False


class ScenarioIntervalFrequencyOverride(BaseModel):
    interval_seconds: float | None = Field(
        default=None,
        gt=0,
    )


class ScenarioLogFrequencyOverride(BaseModel):
    normal_per_second: float | None = Field(
        default=None,
        gt=0,
    )
    warning_per_second: float | None = Field(
        default=None,
        gt=0,
    )
    failure_per_second: float | None = Field(
        default=None,
        gt=0,
    )


class ScenarioFrequencyOverride(BaseModel):
    metrics: (
        ScenarioIntervalFrequencyOverride | None
    ) = None

    logs: (
        ScenarioLogFrequencyOverride | None
    ) = None

    infrastructure_tests: (
        ScenarioIntervalFrequencyOverride | None
    ) = None


class ScenarioDefinition(BaseModel):
    scenario_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)

    family: ScenarioFamily
    industry: Industry

    target: ScenarioTarget

    risk: RiskLevel

    initial_conditions: list[str] = Field(
        min_length=1
    )

    trigger: ScenarioTrigger

    state_sequence: list[OperationalState] = Field(
        min_length=2
    )

    behaviours: list[ScenarioBehaviour] = Field(
        min_length=1
    )

    frequency: ScenarioFrequencyOverride | None = None

    expected_result: ExpectedScenarioResult

    assumptions: list[str] = Field(
        default_factory=list
    )

    tags: list[str] = Field(
        default_factory=list
    )

    @model_validator(mode="after")
    def validate_definition(self) -> "ScenarioDefinition":
        if (
            self.expected_result.scenario_id
            != self.scenario_id
        ):
            raise ValueError(
                "Expected Scenario Result must reference "
                "the same scenario_id."
            )

        if (
            self.state_sequence[0]
            != OperationalState.INITIALISING
        ):
            raise ValueError(
                "Scenario state sequence must begin "
                "with INITIALISING."
            )

        if (
            self.state_sequence[-1]
            != OperationalState.COMPLETED
        ):
            raise ValueError(
                "Scenario state sequence must end "
                "with COMPLETED."
            )

        for current, next_state in zip(
            self.state_sequence,
            self.state_sequence[1:],
            strict=False,
        ):
            if current == next_state:
                raise ValueError(
                    "Scenario state sequence cannot contain "
                    "duplicate adjacent states."
                )

        available_states = set(self.state_sequence)

        for behaviour in self.behaviours:
            if behaviour.during_state not in available_states:
                raise ValueError(
                    f"Behaviour profile {behaviour.profile_id} "
                    "references a state not used by the Scenario."
                )

        return self