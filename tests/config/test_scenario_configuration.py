from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)


def test_bank_01_configuration_loads() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    assert scenario.scenario_id == "BANK-01"

    assert (
        scenario.target.enterprise_id
        == "bank_alpha"
    )

    assert (
        scenario.target.business_stream_id
        == "payments"
    )

    assert (
        scenario.target.service_id
        == "payment_service"
    )

    assert len(scenario.behaviours) == 9