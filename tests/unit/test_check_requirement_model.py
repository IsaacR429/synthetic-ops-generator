from __future__ import annotations

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.checks.catalogue import (
    APPLICATION_POST_DEPLOYMENT_SMOKE,
    INFRASTRUCTURE_CONNECTIVITY,
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


def test_requirement_references_canonical_definition_identity() -> None:
    requirement = CheckRequirement(
        requirement_id="REQ-CHANGE-SMOKE-001",
        check_definition_id=(
            APPLICATION_POST_DEPLOYMENT_SMOKE.check_definition_id
        ),
        obligation=RequirementObligation.REQUIRED,
        evidence_requirement=EvidenceRequirement(),
        rationale=(
            "Post-change validation is required before "
            "release readiness can be confirmed."
        ),
        source_reference="CHANGE-STD-4.2",
    )

    assert (
        requirement.check_definition_id
        == "application.post_deployment_smoke"
    )


def test_requirement_does_not_duplicate_definition_semantics() -> None:
    fields = CheckRequirement.model_fields

    assert "test_type" not in fields
    assert "name" not in fields
    assert "category" not in fields
    assert "applicability" not in fields


def test_requirement_does_not_contain_synthetic_execution_semantics() -> None:
    fields = CheckRequirement.model_fields

    assert "mandatory" not in fields
    assert "profile_id" not in fields
    assert "scenario_id" not in fields
    assert "result" not in fields


def test_requirement_does_not_contain_temporal_program_semantics() -> None:
    fields = CheckRequirement.model_fields

    assert "schedule" not in fields
    assert "frequency" not in fields
    assert "window" not in fields
    assert "cycle" not in fields


def test_requirement_does_not_duplicate_metric_threshold_policy() -> None:
    fields = CheckRequirement.model_fields

    assert "warning_threshold" not in fields
    assert "blocking_threshold" not in fields
    assert "reference_target" not in fields


def test_evidence_requirement_defaults_to_executed_success() -> None:
    requirement = EvidenceRequirement()

    assert requirement.accepted_execution_statuses == {
        ExecutionStatus.EXECUTED,
    }

    assert requirement.accepted_results == {
        Result.PASSED,
    }


def test_evidence_requirement_can_express_presence_without_success() -> None:
    requirement = EvidenceRequirement(
        accepted_execution_statuses={
            ExecutionStatus.EXECUTED,
        },
        accepted_results={
            Result.PASSED,
            Result.FAILED,
        },
    )

    assert requirement.accepted_results == {
        Result.PASSED,
        Result.FAILED,
    }


def test_requirement_supports_required_and_recommended_obligations() -> None:
    required = CheckRequirement(
        requirement_id="REQ-INFRA-001",
        check_definition_id=(
            INFRASTRUCTURE_CONNECTIVITY.check_definition_id
        ),
        obligation=RequirementObligation.REQUIRED,
        evidence_requirement=EvidenceRequirement(),
        rationale="Required infrastructure reachability assurance.",
    )

    recommended = required.model_copy(
        update={
            "requirement_id": "REQ-INFRA-002",
            "obligation": RequirementObligation.RECOMMENDED,
        }
    )

    assert required.obligation == RequirementObligation.REQUIRED
    assert (
        recommended.obligation
        == RequirementObligation.RECOMMENDED
    )


def test_requirement_requires_stable_identity() -> None:
    with pytest.raises(ValidationError):
        CheckRequirement(
            requirement_id="",
            check_definition_id=(
                APPLICATION_POST_DEPLOYMENT_SMOKE
                .check_definition_id
            ),
            obligation=RequirementObligation.REQUIRED,
            evidence_requirement=EvidenceRequirement(),
            rationale="Required validation.",
        )


def test_requirement_requires_canonical_check_identity() -> None:
    with pytest.raises(ValidationError):
        CheckRequirement(
            requirement_id="REQ-BAD-001",
            check_definition_id="",
            obligation=RequirementObligation.REQUIRED,
            evidence_requirement=EvidenceRequirement(),
            rationale="Invalid requirement.",
        )


def test_requirement_requires_rationale() -> None:
    with pytest.raises(ValidationError):
        CheckRequirement(
            requirement_id="REQ-BAD-002",
            check_definition_id=(
                APPLICATION_POST_DEPLOYMENT_SMOKE
                .check_definition_id
            ),
            obligation=RequirementObligation.REQUIRED,
            evidence_requirement=EvidenceRequirement(),
            rationale="",
        )


def test_source_reference_is_provenance_hook_not_full_policy() -> None:
    requirement = CheckRequirement(
        requirement_id="REQ-GOV-001",
        check_definition_id=(
            APPLICATION_POST_DEPLOYMENT_SMOKE
            .check_definition_id
        ),
        obligation=RequirementObligation.REQUIRED,
        evidence_requirement=EvidenceRequirement(),
        rationale="Required by release-governance control.",
        source_reference="CHANGE-STD-4.2",
    )

    assert requirement.source_reference == "CHANGE-STD-4.2"

    fields = CheckRequirement.model_fields

    assert "policy_owner" not in fields
    assert "policy_version" not in fields
    assert "waiver" not in fields
    assert "override_precedence" not in fields
