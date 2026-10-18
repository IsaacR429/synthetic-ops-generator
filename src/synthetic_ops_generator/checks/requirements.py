from enum import StrEnum

from pydantic import BaseModel, Field

from synthetic_ops_generator.domain.operational_test import (
    TestExecutionStatus,
    TestResult,
)


class RequirementObligation(StrEnum):
    """
    Strength of an operational assurance requirement.

    This is not synthetic generator mandatory state and does not
    represent policy authority, waiver state, or scheduling.
    """

    REQUIRED = "required"
    RECOMMENDED = "recommended"


class EvidenceRequirement(BaseModel):
    """
    Minimum operational-test evidence acceptable for one
    CheckRequirement.

    P2A describes evidence acceptance only. It does not yet perform
    requirement assessment or determine whether evidence is missing,
    failed, insufficient, waived, or superseded.
    """

    accepted_execution_statuses: set[
        TestExecutionStatus
    ] = Field(
        default_factory=lambda: {
            TestExecutionStatus.EXECUTED,
        },
        min_length=1,
    )

    accepted_results: set[TestResult] = Field(
        default_factory=lambda: {
            TestResult.PASSED,
        },
        min_length=1,
    )


class CheckRequirement(BaseModel):
    """
    Context-independent representation of an operational assurance
    obligation against one canonical CheckDefinition.

    The canonical check is referenced by identity rather than
    duplicating test type, name, category, or applicability.

    Full policy/control authority, ownership, versioning, effective
    dates, waivers, exceptions, and precedence intentionally remain
    outside this P2A model.
    """

    requirement_id: str = Field(min_length=1)

    check_definition_id: str = Field(
        min_length=1
    )

    obligation: RequirementObligation

    evidence_requirement: EvidenceRequirement = Field(
        default_factory=EvidenceRequirement
    )

    rationale: str = Field(min_length=1)

    source_reference: str | None = Field(
        default=None,
        min_length=1,
    )
