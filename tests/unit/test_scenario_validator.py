import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.validator import (
    ScenarioValidationError,
    validate_scenario_against_enterprise,
)


def load_valid_objects():
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )

    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    return enterprise, scenario


def test_valid_bank_01_scenario() -> None:
    enterprise, scenario = load_valid_objects()

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_invalid_enterprise_reference_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.enterprise_id = "fake_bank"

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_invalid_service_reference_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.service_id = "fake_service"

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_invalid_component_reference_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.component_ids.append(
        "fake_component"
    )

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_component_from_wrong_service_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.component_ids = [
        "authentication_api"
    ]

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )