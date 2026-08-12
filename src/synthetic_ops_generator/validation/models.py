from pydantic import BaseModel, Field


class ValidationFinding(BaseModel):
    requirement_id: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    message: str = Field(min_length=1)

    event_ids: list[str] = Field(
        default_factory=list
    )


class CrossSourceValidationReport(BaseModel):
    findings: list[ValidationFinding] = Field(
        default_factory=list
    )

    @property
    def is_valid(self) -> bool:
        return not self.findings

    def add_finding(
        self,
        *,
        requirement_id: str,
        rule: str,
        message: str,
        event_ids: list[str] | None = None,
    ) -> None:
        self.findings.append(
            ValidationFinding(
                requirement_id=requirement_id,
                rule=rule,
                message=message,
                event_ids=event_ids or [],
            )
        )