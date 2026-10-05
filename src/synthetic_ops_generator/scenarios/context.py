from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)


class ScenarioExecutionState(BaseModel):
    """
    Mutable state shared by every execution target in one Scenario Run.
    """

    scenario_id: str
    run_id: str
    chg_id: str | None = None

    risk: RiskLevel

    deployment_id: str | None = None
    incident_id: str | None = None

    scenario_state: OperationalState = (
        OperationalState.INITIALISING
    )

    simulation_time: datetime

    sequence_number: int = Field(
        default=0,
        ge=0,
    )
    random_seed: int

    def next_sequence(self) -> int:
        self.sequence_number += 1
        return self.sequence_number


class ScenarioExecutionTarget(BaseModel):
    """
    Immutable evidence identity used by a ScenarioContext facade.

    This represents where evidence is emitted. It does not imply
    failure propagation, root cause, or topology impact.
    """

    model_config = ConfigDict(
        frozen=True,
    )

    business_stream: str
    service: str
    component: str | None = None
    environment: Environment


class ScenarioContext(BaseModel):
    """
    Generator-facing Scenario execution context.

    Run state is shared across target-specific context facades while
    evidence identity remains immutable per facade.

    The existing flat constructor and flat serialization shape are
    preserved for backwards compatibility.
    """

    execution_state: ScenarioExecutionState = Field(
        exclude=True,
        repr=False,
    )
    target: ScenarioExecutionTarget = Field(
        exclude=True,
        repr=False,
    )

    @model_validator(mode="before")
    @classmethod
    def _support_flat_constructor(
        cls,
        value: Any,
    ) -> Any:
        if not isinstance(value, dict):
            return value

        if (
            "execution_state" in value
            or "target" in value
        ):
            return value

        state_fields = (
            "scenario_id",
            "run_id",
            "chg_id",
            "risk",
            "deployment_id",
            "incident_id",
            "scenario_state",
            "simulation_time",
            "sequence_number",
            "random_seed",
        )

        target_fields = (
            "business_stream",
            "service",
            "component",
            "environment",
        )

        return {
            "execution_state": {
                name: value[name]
                for name in state_fields
                if name in value
            },
            "target": {
                name: value[name]
                for name in target_fields
                if name in value
            },
        }

    @computed_field
    @property
    def scenario_id(self) -> str:
        return self.execution_state.scenario_id

    @computed_field
    @property
    def run_id(self) -> str:
        return self.execution_state.run_id

    @computed_field
    @property
    def chg_id(self) -> str | None:
        return self.execution_state.chg_id

    @computed_field
    @property
    def business_stream(self) -> str:
        return self.target.business_stream

    @computed_field
    @property
    def service(self) -> str:
        return self.target.service

    @computed_field
    @property
    def component(self) -> str | None:
        return self.target.component

    @computed_field
    @property
    def environment(self) -> Environment:
        return self.target.environment

    @computed_field
    @property
    def risk(self) -> RiskLevel:
        return self.execution_state.risk

    @computed_field
    @property
    def deployment_id(self) -> str | None:
        return self.execution_state.deployment_id

    @deployment_id.setter
    def deployment_id(
        self,
        value: str | None,
    ) -> None:
        self.execution_state.deployment_id = value

    @computed_field
    @property
    def incident_id(self) -> str | None:
        return self.execution_state.incident_id

    @incident_id.setter
    def incident_id(
        self,
        value: str | None,
    ) -> None:
        self.execution_state.incident_id = value

    @computed_field
    @property
    def scenario_state(self) -> OperationalState:
        return self.execution_state.scenario_state

    @scenario_state.setter
    def scenario_state(
        self,
        value: OperationalState,
    ) -> None:
        self.execution_state.scenario_state = value

    @computed_field
    @property
    def simulation_time(self) -> datetime:
        return self.execution_state.simulation_time

    @simulation_time.setter
    def simulation_time(
        self,
        value: datetime,
    ) -> None:
        self.execution_state.simulation_time = value

    @computed_field
    @property
    def sequence_number(self) -> int:
        return self.execution_state.sequence_number

    @sequence_number.setter
    def sequence_number(
        self,
        value: int,
    ) -> None:
        self.execution_state.sequence_number = value

    @computed_field
    @property
    def random_seed(self) -> int:
        return self.execution_state.random_seed

    def next_sequence(self) -> int:
        return self.execution_state.next_sequence()

    def for_target(
        self,
        target: ScenarioExecutionTarget,
    ) -> "ScenarioContext":
        """
        Create another target facade over this Run's shared state.
        """

        return ScenarioContext(
            execution_state=self.execution_state,
            target=target,
        )