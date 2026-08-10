from datetime import datetime

from pydantic import BaseModel, Field

from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
)


class ScenarioContext(BaseModel):
    scenario_id: str
    run_id: str
    chg_id: str

    business_stream: str
    service: str
    component: str | None = None

    environment: Environment
    risk: RiskLevel

    deployment_id: str | None = None
    incident_id: str | None = None

    scenario_state: OperationalState = OperationalState.INITIALISING

    simulation_time: datetime

    sequence_number: int = Field(default=0, ge=0)
    random_seed: int

    def next_sequence(self) -> int:
        self.sequence_number += 1
        return self.sequence_number