from __future__ import annotations

from datetime import UTC, datetime

from synthetic_ops_generator.checks.assessment import (
    RequirementAssessmentStatus,
    RequirementEvidenceScope,
    assess_check_requirement,
)
from synthetic_ops_generator.checks.catalogue import (
    APPLICATION_POST_DEPLOYMENT_SMOKE,
)
from synthetic_ops_generator.checks.requirements import (
    CheckRequirement,
    EvidenceRequirement,
    RequirementObligation,
)
from synthetic_ops_generator.domain.operational_test import (
    TestExecutionStatus as ExecutionStatus,
    TestResult as Result,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
)
from synthetic_ops_generator.temporal.eligibility import (
    TemporalWindow,
)


CHECK_ID = (
    APPLICATION_POST_DEPLOYMENT_SMOKE.check_definition_id
)


def _dt(
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        10,
        18,
        hour,
        minute,
        tzinfo=UTC,
    )


def _requirement() -> CheckRequirement:
    return CheckRequirement(
        requirement_id="REQ-POST-CHANGE-SMOKE",
        check_definition_id=CHECK_ID,
        obligation=RequirementObligation.REQUIRED,
        evidence_requirement=EvidenceRequirement(
            accepted_execution_statuses={
                ExecutionStatus.EXECUTED,
            },
            accepted_results={
                Result.PASSED,
            },
        ),
        rationale=(
            "Post-change smoke validation must provide "
            "acceptable execution evidence."
        ),
        source_reference="CHANGE-STD-4.2",
    )


def _scope() -> RequirementEvidenceScope:
    return RequirementEvidenceScope(
        run_id="RUN-T2C-001",
        service="claims_service",
        environment="production",
    )


def _window() -> TemporalWindow:
    return TemporalWindow(
        window_id="post-change-validation",
        start_at=_dt(14, 0),
        end_at=_dt(14, 30),
    )


def _row(
    *,
    event_id: str,
    event_time: datetime,
    status: str | None = "executed",
    result: str | None = "passed",
    test_id: str | None = None,
    check_definition_id: str | None = CHECK_ID,
    service: str = "claims_service",
) -> RunEvidenceRow:
    return RunEvidenceRow(
        sequence_number=1,
        event_time=event_time,
        event_id=event_id,
        event_type=(
            "application_test.passed"
            if result == "passed"
            else "application_test.failed"
        ),
        schema_version="1.0",
        source_system="synthetic_application_test",
        source_domain="application_test",
        scenario_id="INS-T2C",
        run_id="RUN-T2C-001",
        behaviour_id="t2c_validation",
        chg_id="CHG-T2C-001",
        business_stream="claims",
        service=service,
        component="claims_api",
        environment="production",
        site_id=None,
        service_instance_id=None,
        synthetic=True,
        raw_event={
            "event_id": event_id,
        },
        check_definition_id=check_definition_id,
        operational_test_id=(
            test_id or f"TST-{event_id}"
        ),
        operational_test_category="application",
        operational_test_type="post_deployment_smoke",
        operational_test_status=status,
        operational_test_result=result,
    )


def test_passing_execution_inside_window_satisfies() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-pass-inside",
                event_time=_dt(14, 15),
                result="passed",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )

    assert assessment.satisfying_event_ids == (
        "evt-pass-inside",
    )


def test_passing_execution_after_window_is_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-pass-late",
                event_time=_dt(14, 45),
                result="passed",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )

    assert assessment.matched_event_ids == (
        "evt-pass-late",
    )

    assert assessment.satisfying_event_ids == ()


def test_failed_execution_after_window_is_not_failed() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-fail-late",
                event_time=_dt(14, 45),
                result="failed",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )

    assert assessment.matched_event_ids == (
        "evt-fail-late",
    )


def test_failed_execution_inside_window_is_failed() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-fail-inside",
                event_time=_dt(14, 15),
                result="failed",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.FAILED
    )


def test_out_of_window_pass_does_not_override_in_window_failure() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-fail-inside",
                event_time=_dt(14, 10),
                result="failed",
            ),
            _row(
                event_id="evt-pass-late",
                event_time=_dt(14, 45),
                result="passed",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.FAILED
    )

    assert assessment.satisfying_event_ids == ()


def test_in_window_pass_wins_over_out_of_window_failure() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-fail-early",
                event_time=_dt(13, 45),
                result="failed",
            ),
            _row(
                event_id="evt-pass-inside",
                event_time=_dt(14, 15),
                result="passed",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )

    assert assessment.satisfying_event_ids == (
        "evt-pass-inside",
    )


def test_planned_event_inside_window_is_still_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-planned-inside",
                event_time=_dt(14, 15),
                status="planned",
                result=None,
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )

    assert assessment.matched_event_ids == (
        "evt-planned-inside",
    )


def test_planned_time_cannot_be_used_as_execution_time() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-planned-inside",
                event_time=_dt(14, 15),
                status="planned",
                result=None,
                test_id="TST-RERUN",
            ),
            _row(
                event_id="evt-executed-late",
                event_time=_dt(14, 45),
                status="executed",
                result="passed",
                test_id="TST-RERUN",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )

    assert assessment.matched_event_ids == (
        "evt-planned-inside",
        "evt-executed-late",
    )

    assert assessment.matched_operational_test_ids == (
        "TST-RERUN",
    )

    assert assessment.satisfying_event_ids == ()


def test_no_operationally_matching_evidence_remains_missing() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-other-service",
                event_time=_dt(14, 15),
                service="policy_service",
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )

    assert assessment.matched_event_ids == ()


def test_without_temporal_window_existing_semantics_are_preserved() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-late-without-window",
                event_time=_dt(18, 0),
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )


def test_temporal_window_boundaries_are_inclusive() -> None:
    at_start = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-at-start",
                event_time=_dt(14, 0),
            ),
        ],
        temporal_window=_window(),
    )

    at_end = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-at-end",
                event_time=_dt(14, 30),
            ),
        ],
        temporal_window=_window(),
    )

    assert (
        at_start.status
        == RequirementAssessmentStatus.SATISFIED
    )

    assert (
        at_end.status
        == RequirementAssessmentStatus.SATISFIED
    )
