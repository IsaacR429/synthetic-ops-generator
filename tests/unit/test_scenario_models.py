import pytest
from pydantic import ValidationError

from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)


def test_expected_result_scenario_id_must_match() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    data = scenario.model_dump()

    data["expected_result"]["scenario_id"] = "BANK-99"

    with pytest.raises(ValidationError):
        type(scenario).model_validate(data)


def test_behaviour_state_must_exist_in_sequence() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    data = scenario.model_dump()

    data["behaviours"][0]["during_state"] = "failure"

    with pytest.raises(ValidationError):
        type(scenario).model_validate(data)