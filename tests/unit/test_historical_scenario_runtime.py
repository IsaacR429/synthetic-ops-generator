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
from synthetic_ops_generator.scenarios.models import (
    ScenarioMetricSelection,
    SourceDomain,
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
            "payment_processing_nominal",
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

    assert set(
        runtime.metric_runtime
        .baseline_profile.metrics
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert set(
        runtime.historical_profile.metric_responses
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert set(
        runtime.historical_runtime_profile
        .metric_responses
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


def test_historical_runtime_rejects_contextual_metric_selection() -> None:
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
    behaviours = list(
        scenario.behaviours
    )
    metric_index = next(
        index
        for index, behaviour
        in enumerate(behaviours)
        if behaviour.source == SourceDomain.METRIC
    )
    behaviours[metric_index] = (
        behaviours[metric_index].model_copy(
            update={
                "selection": (
                    ScenarioMetricSelection(
                        metric_ids=[
                            "throughput"
                        ]
                    )
                )
            }
        )
    )
    modified_scenario = scenario.model_copy(
        update={
            "behaviours": behaviours
        }
    )
    with pytest.raises(
        ValueError,
        match=(
            "Historical execution currently "
            "supports only benchmark-evaluable "
            "Metrics.*throughput"
        ),
    ):
        build_historical_scenario_runtime(
            scenario=modified_scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
        )
