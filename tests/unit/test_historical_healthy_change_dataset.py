from datetime import UTC, datetime
from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.history.healthy_change_dataset import (
    HistoricalHealthyChangeDataset,
    HistoricalHealthyChangeMetricPoint,
    HistoricalHealthyChangeMetricSeries,
    build_historical_healthy_change_dataset,
)
from synthetic_ops_generator.history.scenario_runtime import (
    build_historical_scenario_runtime,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

CHANGE_TIME = datetime(
    2026,
    8,
    14,
    10,
    0,
    tzinfo=UTC,
)

CONFIG_ROOT = Path("config")


def build_real_healthy_dataset(
    *,
    scenario_path: Path,
    enterprise_path: Path,
    seed: int = 42,
    post_change_samples: int = 6,
) -> HistoricalHealthyChangeDataset:
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

    return (
        build_historical_healthy_change_dataset(
            runtime=runtime,
            anchor_time=CHANGE_TIME,
            post_change_samples=(
                post_change_samples
            ),
            random_source=SimulationRandom(
                seed=seed
            ),
        )
    )


def test_historical_healthy_change_dataset_constructs() -> None:
    pre_change = (
        HistoricalHealthyChangeMetricPoint(
            timestamp=datetime(
                2026,
                8,
                14,
                9,
                55,
                tzinfo=UTC,
            ),
            operational_state=(
                OperationalState.NORMAL
            ),
            counterfactual_value=180.0,
            observed_value=182.0,
            classification=(
                MetricClassification.NORMAL
            ),
        )
    )

    post_change = (
        HistoricalHealthyChangeMetricPoint(
            timestamp=datetime(
                2026,
                8,
                14,
                10,
                5,
                tzinfo=UTC,
            ),
            operational_state=(
                OperationalState.OBSERVING
            ),
            counterfactual_value=181.0,
            observed_value=183.0,
            classification=(
                MetricClassification.NORMAL
            ),
        )
    )

    series = (
        HistoricalHealthyChangeMetricSeries(
            metric_definition_id=(
                "request_latency"
            ),
            points=(
                pre_change,
                post_change,
            ),
        )
    )

    dataset = HistoricalHealthyChangeDataset(
        scenario_id="BANK-01",
        enterprise_id="bank_alpha",
        service_id="payment_service",
        baseline_profile_id=(
            "critical_interactive_nominal"
        ),
        benchmark_profile_id=(
            "critical_interactive_transaction"
        ),
        change_boundary_time=CHANGE_TIME,
        sample_interval_seconds=300,
        metric_series={
            "request_latency": series,
        },
    )

    assert dataset.scenario_id == "BANK-01"

    assert (
        dataset.change_boundary_time
        == CHANGE_TIME
    )

    assert (
        dataset.metric_series[
            "request_latency"
        ].points[0].operational_state
        == OperationalState.NORMAL
    )

    assert (
        dataset.metric_series[
            "request_latency"
        ].points[1].operational_state
        == OperationalState.OBSERVING
    )


def test_healthy_metric_points_require_no_rollback_metadata() -> None:
    point = HistoricalHealthyChangeMetricPoint(
        timestamp=datetime(
            2026,
            8,
            14,
            10,
            5,
            tzinfo=UTC,
        ),
        operational_state=(
            OperationalState.OBSERVING
        ),
        counterfactual_value=180.0,
        observed_value=181.0,
        classification=(
            MetricClassification.NORMAL
        ),
    )

    assert (
        point.operational_state
        == OperationalState.OBSERVING
    )

    assert not hasattr(
        point,
        "perturbation_strength",
    )

    assert not hasattr(
        point,
        "perturbation_phase",
    )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
    ),
    [
        (
            Path(
                "config/scenarios/banking/"
                "BANK-01.yaml"
            ),
            Path(
                "config/enterprises/"
                "bank_alpha"
            ),
            "BANK-01",
            "payment_service",
        ),
        (
            Path(
                "config/scenarios/insurance/"
                "INS-01.yaml"
            ),
            Path(
                "config/enterprises/"
                "insurer_alpha"
            ),
            "INS-01",
            "claims_service",
        ),
    ],
)
def test_builds_real_healthy_change_dataset(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
) -> None:
    dataset = build_real_healthy_dataset(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    assert (
        dataset.scenario_id
        == expected_scenario
    )

    assert (
        dataset.service_id
        == expected_service
    )

    assert set(
        dataset.metric_series
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }


def test_healthy_dataset_contains_complete_pre_and_post_change_windows() -> None:
    dataset = build_real_healthy_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    assert all(
        len(series.points) == 12
        for series
        in dataset.metric_series.values()
    )


def test_healthy_dataset_preserves_change_boundary_without_emitting_it() -> None:
    dataset = build_real_healthy_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    assert (
        dataset.change_boundary_time
        == CHANGE_TIME
    )

    assert all(
        point.timestamp
        != dataset.change_boundary_time
        for series
        in dataset.metric_series.values()
        for point in series.points
    )


def test_healthy_dataset_aligns_pre_and_post_change_states() -> None:
    dataset = build_real_healthy_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    latency = dataset.metric_series[
        "request_latency"
    ]

    states = tuple(
        point.operational_state
        for point in latency.points
    )

    assert states[:6] == (
        OperationalState.NORMAL,
    ) * 6

    assert states[6:] == (
        OperationalState.OBSERVING,
    ) * 6


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    [
        (
            Path(
                "config/scenarios/banking/"
                "BANK-01.yaml"
            ),
            Path(
                "config/enterprises/"
                "bank_alpha"
            ),
        ),
        (
            Path(
                "config/scenarios/insurance/"
                "INS-01.yaml"
            ),
            Path(
                "config/enterprises/"
                "insurer_alpha"
            ),
        ),
    ],
)
def test_healthy_change_metrics_remain_normal(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    dataset = build_real_healthy_dataset(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    assert all(
        point.classification
        == MetricClassification.NORMAL
        for series
        in dataset.metric_series.values()
        for point in series.points
    )


def test_healthy_dataset_supports_configurable_post_change_samples() -> None:
    dataset = build_real_healthy_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        post_change_samples=4,
    )

    assert all(
        len(series.points) == 10
        for series
        in dataset.metric_series.values()
    )


def test_healthy_dataset_requires_post_change_samples() -> None:
    with pytest.raises(
        ValueError,
        match="sample count",
    ):
        build_real_healthy_dataset(
            scenario_path=Path(
                "config/scenarios/banking/"
                "BANK-01.yaml"
            ),
            enterprise_path=Path(
                "config/enterprises/"
                "bank_alpha"
            ),
            post_change_samples=0,
        )


def test_healthy_dataset_is_reproducible_for_same_seed() -> None:
    kwargs = {
        "scenario_path": Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        "enterprise_path": Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        "seed": 42,
    }

    assert (
        build_real_healthy_dataset(
            **kwargs
        )
        == build_real_healthy_dataset(
            **kwargs
        )
    )


def test_healthy_dataset_varies_for_different_seed() -> None:
    first = build_real_healthy_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        seed=42,
    )

    second = build_real_healthy_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        seed=43,
    )

    assert first != second
