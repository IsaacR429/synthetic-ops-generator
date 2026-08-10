from pydantic import BaseModel, Field

from synthetic_ops_generator.domain.enums import (
    Action,
    Decision,
    Outcome,
)


class ExpectedScenarioResult(BaseModel):
    scenario_id: str

    expected_decision: Decision | None = None
    expected_action: Action | None = None
    expected_outcome: Outcome

    expected_blocking_conditions: list[str] = Field(default_factory=list)
    expected_evidence: list[str] = Field(default_factory=list)

    expected_incident_attribution: bool | None = None

    expected_root_cause: str | None = None
    expected_insight: str | None = None