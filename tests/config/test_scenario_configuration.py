import pytest

from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioFamily,
    SourceDomain,
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


def test_bank_03_operational_degradation_configuration_loads() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )
    assert scenario.scenario_id == "BANK-03"
    assert (
        scenario.family
        == ScenarioFamily.OPERATIONAL_DEGRADATION
    )
    assert (
        scenario.correlation.change_required
        is False
    )
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
    assert len(scenario.behaviours) == 10


HEALTH_METRIC_IDS = (
    "request_latency",
    "error_rate",
    "availability",
)


@pytest.mark.parametrize(
    "scenario_path",
    [
        "config/scenarios/banking/BANK-01.yaml",
        "config/scenarios/banking/BANK-02.yaml",
        "config/scenarios/banking/BANK-03.yaml",
        "config/scenarios/banking/BANK-07.yaml",
    ],
)
def test_existing_payment_scenarios_explicitly_select_health_metrics(
    scenario_path: str,
) -> None:
    scenario = load_scenario(scenario_path)
    metric_behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    ]
    assert metric_behaviours
    for behaviour in metric_behaviours:
        assert behaviour.selection is not None
        assert behaviour.selection.metric_ids is not None
        assert (
            tuple(behaviour.selection.metric_ids)
            == HEALTH_METRIC_IDS
        )


SCENARIO_PATHS = (
    "config/scenarios/banking/BANK-01.yaml",
    "config/scenarios/banking/BANK-02.yaml",
    "config/scenarios/banking/BANK-03.yaml",
    "config/scenarios/banking/BANK-04.yaml",
    "config/scenarios/banking/BANK-05.yaml",
    "config/scenarios/banking/BANK-06.yaml",
    "config/scenarios/banking/BANK-07.yaml",
    "config/scenarios/insurance/INS-01.yaml",
    "config/scenarios/insurance/INS-02.yaml",
)


def test_production_scenarios_have_unique_behaviour_ids() -> None:
    for scenario_path in SCENARIO_PATHS:
        scenario = load_scenario(scenario_path)
        behaviour_ids = [
            behaviour.behaviour_id
            for behaviour in scenario.behaviours
        ]
        assert all(
            behaviour_id is not None
            for behaviour_id in behaviour_ids
        ), scenario_path
        assert len(behaviour_ids) == len(
            set(behaviour_ids)
        ), scenario_path
