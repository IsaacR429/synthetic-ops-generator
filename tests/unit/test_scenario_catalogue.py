from pathlib import Path

from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)

SCENARIO_ROOT = (
    Path(__file__).resolve().parents[2]
    / "config"
    / "scenarios"
)


def test_catalogue_lists_available_scenarios() -> None:
    catalogue = ScenarioCatalogue(SCENARIO_ROOT)

    scenarios = catalogue.list_scenarios()

    scenario_ids = [
        scenario.scenario_id
        for scenario in scenarios
    ]

    assert scenario_ids == [
        "BANK-01",
        "BANK-02",
        "BANK-07",
        "INS-01",
        "INS-02",
    ]


def test_catalogue_gets_scenario_by_id() -> None:
    catalogue = ScenarioCatalogue(SCENARIO_ROOT)

    scenario = catalogue.get_scenario("BANK-01")

    assert scenario is not None
    assert scenario.scenario_id == "BANK-01"
    assert scenario.name == "Successful Payment Release"
    assert scenario.target.enterprise_id == "bank_alpha"


def test_catalogue_returns_none_for_unknown_scenario() -> None:
    catalogue = ScenarioCatalogue(SCENARIO_ROOT)

    scenario = catalogue.get_scenario("UNKNOWN")

    assert scenario is None
