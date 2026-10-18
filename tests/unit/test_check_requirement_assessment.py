from __future__ import annotations

from datetime import UTC, datetime

from synthetic_ops_generator.checks.catalogue import (
    APPLICATION_POST_DEPLOYMENT_SMOKE,
)
from synthetic_ops_generator.checks.requirements import (
    CheckRequirement,
    EvidenceRequirement,
    RequirementObligation,
)
from synthetic_ops_generator.checks.assessment import (
    RequirementAssessmentStatus,
    RequirementEvidenceScope,
    assess_check_requirement,
)
from synthetic_ops_generator.domain.operational_test import (
    TestExecutionStatus as ExecutionStatus,
    TestResult as Result,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
)


CHECK_ID = (
    APPLICATION_POST_DEPLOYMENT_SMOKE.check_definition_id
)


def _requirement(
    *,
    accepted_results: set[Result] | None = None,
    obligation: RequirementObligation = (
        RequirementObligation.REQUIRED
    ),
) -> CheckRequirement:
    evidence_requirement = (
        EvidenceRequirement()
        if accepted_results is None
        else EvidenceRequirement(
            accepted_execution_statuses={
                ExecutionStatus.EXECUTED,
            },
            accepted_results=accepted_results,
        )
    )

    return CheckRequirement(
        requirement_id="REQ-POST-CHANGE-SMOKE",
        check_definition_id=CHECK_ID,
        obligation=obligation,
        evidence_requirement=evidence_requirement,
        rationale=(
            "Post-change smoke validation must provide "
            "acceptable execution evidence."
        ),
        source_reference="CHANGE-STD-4.2",
    )


def _scope(
    **overrides,
) -> RequirementEvidenceScope:
    values = {
        "run_id": "RUN-P2B-001",
        "service": "claims_service",
        "environment": "production",
    }
    values.update(overrides)

    return RequirementEvidenceScope(**values)


def _row(
    *,
    event_id: str,
    check_definition_id: str | None = CHECK_ID,
    run_id: str = "RUN-P2B-001",
    service: str = "claims_service",
    component: str | None = "claims_api",
    environment: str = "production",
    chg_id: str | None = "CHG-P2B-001",
    site_id: str | None = None,
    service_instance_id: str | None = None,
    status: str | None = "executed",
    result: str | None = "passed",
    test_id: str | None = None,
) -> RunEvidenceRow:
    return RunEvidenceRow(
        sequence_number=1,
        event_time=datetime(
            2026,
            10,
            18,
            14,
            0,
            tzinfo=UTC,
        ),
        event_id=event_id,
        event_type="application_test.passed",
        schema_version="1.0",
        source_system="synthetic_application_test",
        source_domain="application_test",
        scenario_id="INS-P2B",
        run_id=run_id,
        behaviour_id="p2b_validation",
        chg_id=chg_id,
        business_stream="claims",
        service=service,
        component=component,
        environment=environment,
        site_id=site_id,
        service_instance_id=service_instance_id,
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


def test_no_matching_check_evidence_is_missing() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-other-check",
                check_definition_id=(
                    "application.functional_validation"
                ),
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )
    assert assessment.matched_event_ids == ()


def test_empty_evidence_is_missing() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_planned_but_not_executed_is_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-planned",
                status="planned",
                result=None,
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )
    assert assessment.matched_event_ids == (
        "evt-planned",
    )


def test_executed_failed_validation_is_failed_not_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-failed",
                result="failed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.FAILED
    )
    assert assessment.matched_event_ids == (
        "evt-failed",
    )


def test_executed_passing_validation_satisfies_requirement() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-passed",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )
    assert assessment.satisfying_event_ids == (
        "evt-passed",
    )


def test_presence_oriented_requirement_can_accept_failed_result() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(
            accepted_results={
                Result.PASSED,
                Result.FAILED,
            }
        ),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-executed-failed",
                result="failed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )


def test_success_on_another_service_does_not_satisfy_requirement() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-other-service",
                service="policy_service",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_success_from_another_run_does_not_satisfy_requirement() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-other-run",
                run_id="RUN-OTHER",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_environment_is_part_of_evidence_scope() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-staging",
                environment="staging",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_optional_component_scope_filters_when_declared() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(
            component="claims_api",
        ),
        evidence_rows=[
            _row(
                event_id="evt-other-component",
                component="claims_database",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_unspecified_component_scope_does_not_restrict_component() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-component-pass",
                component="claims_api",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )


def test_optional_change_scope_filters_when_declared() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(
            chg_id="CHG-P2B-001",
        ),
        evidence_rows=[
            _row(
                event_id="evt-other-change",
                chg_id="CHG-OTHER",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_optional_service_instance_scope_filters_when_declared() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(
            service_instance_id="claims-primary",
        ),
        evidence_rows=[
            _row(
                event_id="evt-secondary",
                service_instance_id="claims-secondary",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_malformed_executed_evidence_without_result_is_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-no-result",
                status="executed",
                result=None,
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )


def test_unrecognised_execution_status_is_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-unknown-status",
                status="future_status",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )


def test_satisfying_execution_wins_over_prior_failed_execution() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-first-failed",
                result="failed",
            ),
            _row(
                event_id="evt-rerun-passed",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )

    assert assessment.matched_event_ids == (
        "evt-first-failed",
        "evt-rerun-passed",
    )

    assert assessment.satisfying_event_ids == (
        "evt-rerun-passed",
    )


def test_failed_execution_wins_over_only_incomplete_evidence() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-planned",
                status="planned",
                result=None,
            ),
            _row(
                event_id="evt-failed",
                status="executed",
                result="failed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.FAILED
    )


def test_recommended_obligation_does_not_change_factual_status() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(
            obligation=RequirementObligation.RECOMMENDED,
        ),
        scope=_scope(),
        evidence_rows=[],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )

    assert (
        assessment.obligation
        == RequirementObligation.RECOMMENDED
    )


def test_assessment_preserves_requirement_identity_and_audit_lineage() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-pass",
                test_id="TST-P2B-PASS",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.requirement_id
        == "REQ-POST-CHANGE-SMOKE"
    )
    assert assessment.check_definition_id == CHECK_ID
    assert assessment.matched_event_ids == (
        "evt-pass",
    )
    assert assessment.matched_operational_test_ids == (
        "TST-P2B-PASS",
    )


def test_assessment_model_does_not_determine_policy_blocking() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[],
    )

    fields = assessment.model_fields

    assert "blocking" not in fields
    assert "decision" not in fields
    assert "waived" not in fields
    assert "policy_id" not in fields

def test_definition_identity_is_authoritative_not_test_type() -> None:
    row = _row(
        event_id="evt-same-type-wrong-definition",
        check_definition_id=(
            "application.functional_validation"
        ),
        result="passed",
    )

    # The helper still gives this row the same operational-test type
    # as the requirement. Identity must nevertheless win.
    assert (
        row.operational_test_type
        == "post_deployment_smoke"
    )

    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[row],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_optional_site_scope_filters_when_declared() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(
            site_id="primary-site",
        ),
        evidence_rows=[
            _row(
                event_id="evt-secondary-site",
                site_id="secondary-site",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.MISSING
    )


def test_one_shot_evidence_iterable_is_supported() -> None:
    def evidence_stream():
        yield _row(
            event_id="evt-generator-pass",
            result="passed",
        )

    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=evidence_stream(),
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )

    assert assessment.matched_event_ids == (
        "evt-generator-pass",
    )


def test_planned_and_executed_events_preserve_audit_order_and_test_identity() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-test-planned",
                test_id="TST-P2B-RERUN",
                status="planned",
                result=None,
            ),
            _row(
                event_id="evt-test-executed",
                test_id="TST-P2B-RERUN",
                status="executed",
                result="passed",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.SATISFIED
    )

    assert assessment.matched_event_ids == (
        "evt-test-planned",
        "evt-test-executed",
    )

    # Planning and execution are two evidence events for one
    # operational-test identity.
    assert assessment.matched_operational_test_ids == (
        "TST-P2B-RERUN",
    )

    assert assessment.satisfying_event_ids == (
        "evt-test-executed",
    )


def test_unrecognised_result_is_insufficient() -> None:
    assessment = assess_check_requirement(
        requirement=_requirement(),
        scope=_scope(),
        evidence_rows=[
            _row(
                event_id="evt-future-result",
                status="executed",
                result="future_result",
            ),
        ],
    )

    assert (
        assessment.status
        == RequirementAssessmentStatus.INSUFFICIENT
    )

