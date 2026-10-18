from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.checks.catalogue import (
    APPLICATION_POST_DEPLOYMENT_SMOKE,
)
from synthetic_ops_generator.checks.requirements import (
    CheckRequirement,
    EvidenceRequirement,
    RequirementObligation,
)
from synthetic_ops_generator.domain.enums import (
    AssetClass,
    Environment,
    MissionCriticality,
    RiskLevel,
    ServiceClass,
)
from synthetic_ops_generator.governance.models import (
    GovernanceAuthority,
    GovernanceAuthorityType,
    PolicyApplicability,
    PolicyCatalogue,
    PolicyControl,
    PolicyDocument,
)


def _requirement() -> CheckRequirement:
    return CheckRequirement(
        requirement_id="REQ-CHANGE-SMOKE-001",
        check_definition_id=(
            APPLICATION_POST_DEPLOYMENT_SMOKE
            .check_definition_id
        ),
        obligation=RequirementObligation.REQUIRED,
        evidence_requirement=EvidenceRequirement(),
        rationale=(
            "Production post-change smoke validation "
            "is required."
        ),
        source_reference="ECMS-4.2:CTRL-VAL-01",
    )


def _authority() -> GovernanceAuthority:
    return GovernanceAuthority(
        authority_id="AUTH-CHANGE-MGMT",
        authority_type=(
            GovernanceAuthorityType.ENTERPRISE_STANDARD
        ),
        name="Enterprise Change Management Standard",
        source_reference="ECMS",
    )


def _policy() -> PolicyDocument:
    return PolicyDocument(
        policy_id="POL-CHANGE-0042",
        title="Enterprise Change Management Standard",
        version="4.2",
        owner="Enterprise Change Management",
        authority_id="AUTH-CHANGE-MGMT",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        description=(
            "Enterprise requirements governing "
            "production change assurance."
        ),
    )


def _applicability() -> PolicyApplicability:
    return PolicyApplicability(
        environments={
            Environment.PRODUCTION,
        },
        service_classes={
            ServiceClass.BUSINESS_APPLICATION,
        },
        mission_criticalities={
            MissionCriticality.MISSION_CRITICAL,
        },
        asset_classes={
            AssetClass.APPLICATION,
        },
        change_risks={
            RiskLevel.HIGH,
        },
    )


def _control() -> PolicyControl:
    return PolicyControl(
        control_id="CTRL-POST-CHANGE-VALIDATION",
        policy_id="POL-CHANGE-0042",
        control_reference="4.2.3",
        title="Production post-change validation",
        objective=(
            "Ensure high-risk production changes to "
            "mission-critical applications are validated "
            "before readiness is confirmed."
        ),
        applicability=_applicability(),
        requirement_ids=(
            "REQ-CHANGE-SMOKE-001",
        ),
    )


def test_governance_authority_preserves_source_provenance() -> None:
    authority = _authority()

    assert authority.authority_id == "AUTH-CHANGE-MGMT"
    assert (
        authority.authority_type
        == GovernanceAuthorityType.ENTERPRISE_STANDARD
    )
    assert authority.source_reference == "ECMS"


def test_policy_document_has_version_owner_and_effective_period() -> None:
    policy = _policy()

    assert policy.version == "4.2"
    assert policy.owner == "Enterprise Change Management"
    assert policy.effective_from == date(2026, 1, 1)
    assert policy.effective_to is None


def test_policy_rejects_invalid_effective_period() -> None:
    with pytest.raises(ValidationError):
        PolicyDocument(
            policy_id="POL-BAD",
            title="Invalid Policy",
            version="1.0",
            owner="Governance",
            authority_id="AUTH-CHANGE-MGMT",
            effective_from=date(2026, 6, 1),
            effective_to=date(2026, 5, 31),
        )


def test_control_references_requirement_identity() -> None:
    control = _control()

    assert control.requirement_ids == (
        "REQ-CHANGE-SMOKE-001",
    )


def test_control_does_not_duplicate_check_definition_semantics() -> None:
    fields = PolicyControl.model_fields

    assert "check_definition_id" not in fields
    assert "test_type" not in fields
    assert "accepted_results" not in fields
    assert "mandatory" not in fields


def test_policy_applicability_reuses_enterprise_semantics() -> None:
    applicability = _applicability()

    assert applicability.environments == {
        Environment.PRODUCTION,
    }
    assert applicability.service_classes == {
        ServiceClass.BUSINESS_APPLICATION,
    }
    assert applicability.mission_criticalities == {
        MissionCriticality.MISSION_CRITICAL,
    }
    assert applicability.asset_classes == {
        AssetClass.APPLICATION,
    }
    assert applicability.change_risks == {
        RiskLevel.HIGH,
    }


def test_empty_applicability_dimensions_are_unconstrained() -> None:
    applicability = PolicyApplicability()

    assert applicability.environments == set()
    assert applicability.service_classes == set()
    assert applicability.mission_criticalities == set()
    assert applicability.asset_classes == set()
    assert applicability.change_risks == set()


def test_control_requires_at_least_one_requirement() -> None:
    with pytest.raises(ValidationError):
        PolicyControl(
            control_id="CTRL-EMPTY",
            policy_id="POL-CHANGE-0042",
            control_reference="4.2.9",
            title="Empty control",
            objective="Invalid control.",
            applicability=PolicyApplicability(),
            requirement_ids=(),
        )


def test_control_rejects_duplicate_requirement_references() -> None:
    with pytest.raises(ValidationError):
        PolicyControl(
            control_id="CTRL-DUPLICATE",
            policy_id="POL-CHANGE-0042",
            control_reference="4.2.10",
            title="Duplicate requirement control",
            objective="Invalid duplicate linkage.",
            applicability=PolicyApplicability(),
            requirement_ids=(
                "REQ-CHANGE-SMOKE-001",
                "REQ-CHANGE-SMOKE-001",
            ),
        )


def test_catalogue_preserves_referential_integrity() -> None:
    catalogue = PolicyCatalogue(
        authorities={
            "AUTH-CHANGE-MGMT": _authority(),
        },
        policies={
            "POL-CHANGE-0042": _policy(),
        },
        controls={
            "CTRL-POST-CHANGE-VALIDATION": _control(),
        },
        requirements={
            "REQ-CHANGE-SMOKE-001": _requirement(),
        },
    )

    assert (
        catalogue.controls[
            "CTRL-POST-CHANGE-VALIDATION"
        ].policy_id
        == "POL-CHANGE-0042"
    )


def test_catalogue_rejects_unknown_policy_authority() -> None:
    bad_policy = _policy().model_copy(
        update={
            "authority_id": "AUTH-UNKNOWN",
        }
    )

    with pytest.raises(ValidationError):
        PolicyCatalogue(
            authorities={
                "AUTH-CHANGE-MGMT": _authority(),
            },
            policies={
                bad_policy.policy_id: bad_policy,
            },
            controls={},
            requirements={},
        )


def test_catalogue_rejects_control_with_unknown_policy() -> None:
    bad_control = _control().model_copy(
        update={
            "policy_id": "POL-UNKNOWN",
        }
    )

    with pytest.raises(ValidationError):
        PolicyCatalogue(
            authorities={
                "AUTH-CHANGE-MGMT": _authority(),
            },
            policies={
                "POL-CHANGE-0042": _policy(),
            },
            controls={
                bad_control.control_id: bad_control,
            },
            requirements={
                "REQ-CHANGE-SMOKE-001": _requirement(),
            },
        )


def test_catalogue_rejects_unknown_requirement_reference() -> None:
    bad_control = _control().model_copy(
        update={
            "requirement_ids": (
                "REQ-UNKNOWN",
            ),
        }
    )

    with pytest.raises(ValidationError):
        PolicyCatalogue(
            authorities={
                "AUTH-CHANGE-MGMT": _authority(),
            },
            policies={
                "POL-CHANGE-0042": _policy(),
            },
            controls={
                bad_control.control_id: bad_control,
            },
            requirements={
                "REQ-CHANGE-SMOKE-001": _requirement(),
            },
        )


def test_catalogue_keys_must_match_domain_identity() -> None:
    with pytest.raises(ValidationError):
        PolicyCatalogue(
            authorities={
                "WRONG-AUTHORITY-KEY": _authority(),
            },
            policies={
                "POL-CHANGE-0042": _policy(),
            },
            controls={},
            requirements={},
        )


def test_policy_layer_does_not_duplicate_metric_thresholds() -> None:
    fields = PolicyControl.model_fields

    assert "reference_target" not in fields
    assert "warning_threshold" not in fields
    assert "blocking_threshold" not in fields


def test_policy_layer_does_not_own_runtime_decisions() -> None:
    fields = PolicyControl.model_fields

    assert "decision" not in fields
    assert "action" not in fields
    assert "outcome" not in fields
    assert "blocking" not in fields


def test_p3a_does_not_model_waivers_or_schedules_yet() -> None:
    fields = PolicyControl.model_fields

    assert "waiver" not in fields
    assert "exception" not in fields
    assert "schedule" not in fields
    assert "frequency" not in fields
    assert "validation_window" not in fields
