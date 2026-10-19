import pytest
from pydantic import ValidationError

from synthetic_ops_generator.checks.catalogue import (
    DEFAULT_INFRASTRUCTURE_CHECKS,
    INFRASTRUCTURE_CERTIFICATE_VALIDATION,
    INFRASTRUCTURE_DNS_RESOLUTION,
)
from synthetic_ops_generator.domain.enums import (
    ServiceClass,
)
from synthetic_ops_generator.domain.operational_test import (
    TestCategory as OperationalTestCategory,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioCheckSelection,
)


def test_dns_resolution_is_canonical_infrastructure_check() -> None:
    definition = INFRASTRUCTURE_DNS_RESOLUTION

    assert (
        definition.check_definition_id
        == "infrastructure.dns_resolution"
    )
    assert definition.category == OperationalTestCategory.INFRASTRUCTURE
    assert definition.test_type == "dns_resolution"

    assert (
        ServiceClass.BUSINESS_APPLICATION
        in definition.applicability.service_classes
    )


def test_certificate_validation_is_canonical_infrastructure_check() -> None:
    definition = INFRASTRUCTURE_CERTIFICATE_VALIDATION

    assert (
        definition.check_definition_id
        == "infrastructure.certificate_validation"
    )
    assert definition.category == OperationalTestCategory.INFRASTRUCTURE
    assert definition.test_type == "certificate_validation"

    assert (
        ServiceClass.BUSINESS_APPLICATION
        in definition.applicability.service_classes
    )


def test_new_checks_do_not_change_default_infrastructure_suite() -> None:
    default_ids = {
        spec.definition.check_definition_id
        for spec in DEFAULT_INFRASTRUCTURE_CHECKS
    }

    assert (
        INFRASTRUCTURE_DNS_RESOLUTION.check_definition_id
        not in default_ids
    )
    assert (
        INFRASTRUCTURE_CERTIFICATE_VALIDATION
        .check_definition_id
        not in default_ids
    )


def test_scenario_check_selection_preserves_canonical_ids() -> None:
    selection = ScenarioCheckSelection(
        check_definition_ids=[
            "infrastructure.connectivity",
            "infrastructure.dns_resolution",
            "infrastructure.certificate_validation",
        ]
    )

    assert selection.check_definition_ids == [
        "infrastructure.connectivity",
        "infrastructure.dns_resolution",
        "infrastructure.certificate_validation",
    ]


def test_scenario_check_selection_requires_at_least_one_id() -> None:
    with pytest.raises(ValidationError):
        ScenarioCheckSelection(
            check_definition_ids=[]
        )


def test_scenario_check_selection_rejects_duplicate_ids() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Check selection cannot contain duplicate IDs"
        ),
    ):
        ScenarioCheckSelection(
            check_definition_ids=[
                "infrastructure.dns_resolution",
                "infrastructure.dns_resolution",
            ]
        )
