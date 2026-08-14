from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import numpy as np
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
from synthetic_ops_generator.history.incident_dataset import (
    HistoricalIncidentDataset,
    build_historical_incident_dataset,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.history.scenario_runtime import (
    HistoricalScenarioRuntime,
    build_historical_scenario_runtime,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDirection,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

CONFIG_ROOT = Path("config")

CASES = (
    (
        Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        Path(
            "config/enterprises/"
            "bank_alpha"
        ),
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
    ),
)

SEEDS = tuple(range(1, 25))


def build_runtime(
    *,
    scenario_path: Path,
    enterprise_path: Path,
) -> HistoricalScenarioRuntime:
    scenario = load_scenario(
        scenario_path
    )

    enterprise = (
        load_enterprise_configuration(
            enterprise_path
        )
    )

    return build_historical_scenario_runtime(
        scenario=scenario,
        enterprise=enterprise,
        config_root=CONFIG_ROOT,
    )


def build_dataset(
    *,
    runtime: HistoricalScenarioRuntime,
    seed: int,
) -> HistoricalIncidentDataset:
    return build_historical_incident_dataset(
        runtime=runtime,
        anchor_time=datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        ),
        curve_spec=PerturbationCurveSpec(
            degradation_samples=4,
            plateau_samples=2,
            recovery_samples=4,
        ),
        random_source=SimulationRandom(
            seed=seed
        ),
    )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_healthy_telemetry_varies_across_seeds(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    observations = {
        metric_id: []
        for metric_id
        in runtime.metric_runtime
        .baseline_profile.metrics
    }

    for seed in SEEDS:
        dataset = build_dataset(
            runtime=runtime,
            seed=seed,
        )

        for metric_id, series in (
            dataset.metric_series.items()
        ):
            observations[
                metric_id
            ].extend(
                point.observed_value
                for point in series.points[:6]
            )

    assert all(
        np.std(values) > 0.0
        for values
        in observations.values()
    )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_healthy_telemetry_remains_normal_across_seeds(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for seed in SEEDS:
        dataset = build_dataset(
            runtime=runtime,
            seed=seed,
        )

        for series in (
            dataset.metric_series.values()
        ):
            assert all(
                point.classification
                == MetricClassification.NORMAL
                for point
                in series.points[:6]
            )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_every_run_reaches_blocking_incident_peak(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for seed in SEEDS:
        dataset = build_dataset(
            runtime=runtime,
            seed=seed,
        )

        for metric_id, series in (
            dataset.metric_series.items()
        ):
            benchmark = (
                runtime.metric_runtime
                .resolved_benchmarks[
                    metric_id
                ]
            )

            peak_points = tuple(
                point
                for point in series.points
                if (
                    point.perturbation_strength
                    == 1.0
                )
            )

            assert peak_points

            assert all(
                point.classification
                == MetricClassification.BLOCKING
                for point in peak_points
            )

            assert all(
                point.observed_value
                == pytest.approx(
                    benchmark.blocking_threshold
                )
                for point in peak_points
            )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_every_run_recovers_to_normal(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for seed in SEEDS:
        dataset = build_dataset(
            runtime=runtime,
            seed=seed,
        )

        for series in (
            dataset.metric_series.values()
        ):
            final_point = (
                series.points[-1]
            )

            assert (
                final_point.operational_state
                == OperationalState.RECOVERY
            )

            assert (
                final_point.perturbation_strength
                == 0.0
            )

            assert (
                final_point.classification
                == MetricClassification.NORMAL
            )

            assert (
                final_point.observed_value
                == pytest.approx(
                    final_point
                    .counterfactual_value
                )
            )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_degradation_direction_is_stable_across_seeds(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for seed in SEEDS:
        dataset = build_dataset(
            runtime=runtime,
            seed=seed,
        )

        for metric_id, series in (
            dataset.metric_series.items()
        ):
            definition = (
                runtime.metric_runtime
                .definitions[
                    metric_id
                ]
            )

            degradation = tuple(
                point.observed_value
                for point in series.points
                if (
                    point.operational_state
                    in {
                        OperationalState.OBSERVING,
                        OperationalState.DEGRADED,
                    }
                )
            )

            if (
                definition.direction
                == MetricDirection.LOWER_IS_BETTER
            ):
                assert all(
                    current <= following
                    for current, following
                    in pairwise(degradation)
                )

            elif (
                definition.direction
                == MetricDirection.HIGHER_IS_BETTER
            ):
                assert all(
                    current >= following
                    for current, following
                    in pairwise(degradation)
                )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_healthy_metric_residuals_are_not_tightly_coupled(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    residuals: dict[
        str,
        list[float],
    ] = {
        metric_id: []
        for metric_id
        in runtime.metric_runtime
        .baseline_profile.metrics
    }

    for seed in SEEDS:
        dataset = build_dataset(
            runtime=runtime,
            seed=seed,
        )

        for metric_id, series in (
            dataset.metric_series.items()
        ):
            for point in series.points[:6]:
                residuals[
                    metric_id
                ].append(
                    point.observed_value
                    - point.counterfactual_value
                )

    metric_ids = sorted(
        residuals
    )

    for index, first_id in enumerate(
        metric_ids
    ):
        for second_id in (
            metric_ids[index + 1 :]
        ):
            correlation = float(
                np.corrcoef(
                    residuals[first_id],
                    residuals[second_id],
                )[0, 1]
            )

            assert abs(correlation) < 0.35


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    CASES,
)
def test_incident_metrics_share_strong_scenario_signal(
    scenario_path: Path,
    enterprise_path: Path,
) -> None:
    runtime = build_runtime(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    dataset = build_dataset(
        runtime=runtime,
        seed=42,
    )

    latency = np.array(
        [
            point.observed_value
            for point in dataset.metric_series[
                "request_latency"
            ].points[6:]
        ]
    )

    errors = np.array(
        [
            point.observed_value
            for point in dataset.metric_series[
                "error_rate"
            ].points[6:]
        ]
    )

    availability = np.array(
        [
            point.observed_value
            for point in dataset.metric_series[
                "availability"
            ].points[6:]
        ]
    )

    latency_error = float(
        np.corrcoef(
            latency,
            errors,
        )[0, 1]
    )

    latency_availability = float(
        np.corrcoef(
            latency,
            availability,
        )[0, 1]
    )

    assert latency_error > 0.90

    assert (
        latency_availability
        < -0.90
    )
