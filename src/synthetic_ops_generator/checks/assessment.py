from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from synthetic_ops_generator.checks.requirements import (
    CheckRequirement,
    RequirementObligation,
)
from synthetic_ops_generator.domain.operational_test import (
    TestExecutionStatus,
    TestResult,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
)
from synthetic_ops_generator.temporal.eligibility import (
    TemporalWindow,
    assess_temporal_eligibility,
)


class RequirementAssessmentStatus(StrEnum):
    """
    Factual result of comparing one requirement with observed evidence.

    Policy blocking, waivers, decisions, and temporal precedence are
    intentionally outside this assessment.
    """

    SATISFIED = "satisfied"
    FAILED = "failed"
    MISSING = "missing"
    INSUFFICIENT = "insufficient"


class RequirementEvidenceScope(BaseModel):
    """
    Operational scope in which observed check evidence may satisfy
    a requirement.

    Required dimensions prevent an execution from another run,
    service, or environment from satisfying the requirement.

    Optional dimensions constrain matching only when declared.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str = Field(min_length=1)
    service: str = Field(min_length=1)
    environment: str = Field(min_length=1)

    component: str | None = Field(
        default=None,
        min_length=1,
    )
    chg_id: str | None = Field(
        default=None,
        min_length=1,
    )
    site_id: str | None = Field(
        default=None,
        min_length=1,
    )
    service_instance_id: str | None = Field(
        default=None,
        min_length=1,
    )


class RequirementAssessment(BaseModel):
    """
    Auditable factual assessment of one CheckRequirement.

    Obligation strength is preserved but does not change factual
    status. Whether a result blocks readiness is a later policy concern.
    """

    model_config = ConfigDict(frozen=True)

    requirement_id: str = Field(min_length=1)
    check_definition_id: str = Field(min_length=1)

    obligation: RequirementObligation
    status: RequirementAssessmentStatus

    scope: RequirementEvidenceScope

    matched_event_ids: tuple[str, ...] = ()
    matched_operational_test_ids: tuple[str, ...] = ()
    satisfying_event_ids: tuple[str, ...] = ()


def _matches_scope(
    row: RunEvidenceRow,
    scope: RequirementEvidenceScope,
) -> bool:
    if row.run_id != scope.run_id:
        return False

    if row.service != scope.service:
        return False

    if row.environment != scope.environment:
        return False

    optional_dimensions = (
        ("component", scope.component),
        ("chg_id", scope.chg_id),
        ("site_id", scope.site_id),
        (
            "service_instance_id",
            scope.service_instance_id,
        ),
    )

    for field_name, expected in optional_dimensions:
        if expected is None:
            continue

        if getattr(row, field_name) != expected:
            return False

    return True


def _unique_non_null(
    values: Iterable[str | None],
) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []

    for value in values:
        if value is None or value in seen:
            continue

        seen.add(value)
        ordered.append(value)

    return tuple(ordered)


def _execution_status(
    value: str | None,
) -> TestExecutionStatus | None:
    if value is None:
        return None

    try:
        return TestExecutionStatus(value)
    except ValueError:
        return None


def _result(
    value: str | None,
) -> TestResult | None:
    if value is None:
        return None

    try:
        return TestResult(value)
    except ValueError:
        return None


def assess_check_requirement(
    *,
    requirement: CheckRequirement,
    scope: RequirementEvidenceScope,
    evidence_rows: Iterable[RunEvidenceRow],
    temporal_window: TemporalWindow | None = None,
) -> RequirementAssessment:
    """
    Compare one operational check requirement with observed evidence.

    Precedence:
      1. no scoped evidence -> MISSING
      2. accepted successful execution -> SATISFIED
      3. accepted execution with unacceptable definitive result
         -> FAILED
      4. evidence exists but cannot satisfy evaluation semantics
         -> INSUFFICIENT

    Input ordering is preserved for audit lineage.

    When temporal_window is supplied, only accepted executed evidence
    inside that window may satisfy or fail the requirement. Scoped
    evidence outside the window remains matched audit evidence and
    therefore leads to INSUFFICIENT rather than MISSING when no
    temporally eligible execution exists.

    Latest-attempt semantics remain outside this assessment.
    """

    matched = tuple(
        row
        for row in evidence_rows
        if (
            row.check_definition_id
            == requirement.check_definition_id
            and _matches_scope(
                row,
                scope,
            )
        )
    )

    if not matched:
        return RequirementAssessment(
            requirement_id=requirement.requirement_id,
            check_definition_id=(
                requirement.check_definition_id
            ),
            obligation=requirement.obligation,
            status=RequirementAssessmentStatus.MISSING,
            scope=scope,
        )

    satisfying_event_ids: list[str] = []
    failed_execution_found = False

    accepted_statuses = (
        requirement
        .evidence_requirement
        .accepted_execution_statuses
    )
    accepted_results = (
        requirement
        .evidence_requirement
        .accepted_results
    )

    for row in matched:
        status = _execution_status(
            row.operational_test_status
        )

        if (
            status is None
            or status not in accepted_statuses
        ):
            continue

        if temporal_window is not None:
            temporal_eligibility = (
                assess_temporal_eligibility(
                    observed_at=row.event_time,
                    window=temporal_window,
                )
            )

            if not temporal_eligibility.is_eligible:
                continue

        result = _result(
            row.operational_test_result
        )

        if result is None:
            continue

        if result in accepted_results:
            satisfying_event_ids.append(
                row.event_id
            )
        else:
            failed_execution_found = True

    if satisfying_event_ids:
        assessment_status = (
            RequirementAssessmentStatus.SATISFIED
        )
    elif failed_execution_found:
        assessment_status = (
            RequirementAssessmentStatus.FAILED
        )
    else:
        assessment_status = (
            RequirementAssessmentStatus.INSUFFICIENT
        )

    return RequirementAssessment(
        requirement_id=requirement.requirement_id,
        check_definition_id=(
            requirement.check_definition_id
        ),
        obligation=requirement.obligation,
        status=assessment_status,
        scope=scope,
        matched_event_ids=tuple(
            row.event_id
            for row in matched
        ),
        matched_operational_test_ids=(
            _unique_non_null(
                row.operational_test_id
                for row in matched
            )
        ),
        satisfying_event_ids=tuple(
            satisfying_event_ids
        ),
    )
