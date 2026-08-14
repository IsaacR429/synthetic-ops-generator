from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.history.scenario_runtime import (
    build_historical_scenario_runtime,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

CONFIG_ROOT = Path("config")


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    [
        (
            Path(
                "config/scenarios/banking/"
                "BANK-02.yaml"
            ),
            Path(
                "config/enterprises/"
                "bank_alpha"
            ),
            "payment_service",
            "critical_interactive_nominal",
            "critical_interactive_transaction",
        ),
        (
            Path(
                "config/scenarios/insurance/"
                "INS-02.yaml"
            ),
            Path(
                "config/enterprises/"
                "insurer_alpha"
            ),
            "claims_service",
            "business_workflow_nominal",
            "business_critical_interactive",
        ),
    ],
)
def test_builds_real_historical_scenario_runtime(
    scenario_path: Path,
    enterprise_path: Path,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    scenario = load_scenario(
        scenario_path
    )

    enterprise = (
        load_enterprise_configuration(
            enterprise_path
        )
    )

    runtime = (
        build_historical_scenario_runtime(
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
        )
    )

    assert (
        runtime.service.service_id
        == expected_service
    )

    assert (
        runtime.metric_runtime
        .baseline_profile.profile_id
        == expected_baseline
    )

    assert (
        runtime.historical_profile.profile_id
        == expected_baseline
    )

    assert (
        runtime.historical_runtime_profile.profile_id
        == expected_baseline
    )

    assert (
        runtime.metric_runtime
        .benchmark_profile_id
        == expected_benchmark
    )

    assert set(
        runtime.metric_runtime.resolved_benchmarks
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }


def test_historical_runtime_rejects_wrong_enterprise(
) -> None:
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-02.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "insurer_alpha"
        )
    )

    with pytest.raises(
        ValueError,
        match="does not match",
    ):
        build_historical_scenario_runtime(
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
        )


def test_historical_runtime_rejects_missing_target_service(
) -> None:
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-02.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    modified_scenario = scenario.model_copy(
        update={
            "target": scenario.target.model_copy(
                update={"service_id": "nonexistent_service"}
            )
        }
    )

    with pytest.raises(
        ValueError,
        match="Scenario target Service was not found",
    ):
        build_historical_scenario_runtime(
            scenario=modified_scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
        )
