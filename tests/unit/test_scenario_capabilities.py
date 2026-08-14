from pathlib import Path

import pytest

from synthetic_ops_generator.scenarios.capabilities import (
    resolve_scenario_execution_capabilities,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)

CONFIG_ROOT = Path("config")


@pytest.mark.parametrize(
    (
        "scenario_id",
        "historical_supported",
    ),
    [
        ("BANK-01", False),
        ("BANK-02", True),
        ("BANK-07", False),
        ("INS-01", False),
        ("INS-02", True),
    ],
)
def test_scenario_execution_capabilities(
    scenario_id: str,
    historical_supported: bool,
) -> None:
    catalogue = ScenarioCatalogue(
        CONFIG_ROOT / "scenarios"
    )

    scenario = catalogue.get_scenario(
        scenario_id
    )

    assert scenario is not None

    capabilities = (
        resolve_scenario_execution_capabilities(
            scenario
        )
    )

    assert (
        capabilities.standard_supported
        is True
    )

    assert (
        capabilities.historical_supported
        is historical_supported
    )
