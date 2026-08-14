import itertools
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
        "BANK-02",
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
        "INS-02",
        "claims_service",
        "business_workflow_nominal",
        "business_critical_interactive",
    ),
)


def build_case(
    *,
    scenario_path: Path,
    enterprise_path: Path,
    seed: int = 42,
) -> tuple[
    HistoricalScenarioRuntime,
    HistoricalIncidentDataset,
]:
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

    dataset = (
        build_historical_incident_dataset(
            runtime=runtime,
            anchor_time=datetime(
                2026,
                8,
                14,
                10,
                0,
                tzinfo=UTC,
            ),
            curve_spec=(
                PerturbationCurveSpec(
                    degradation_samples=4,
                    plateau_samples=2,
                    recovery_samples=4,
                )
            ),
            random_source=(
                SimulationRandom(
                    seed=seed
                )
            ),
        )
    )

    return runtime, dataset


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_real_regression_scenarios_build_complete_history(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    _, dataset = build_case(
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

    assert (
        dataset.baseline_profile_id
        == expected_baseline
    )

    assert (
        dataset.benchmark_profile_id
        == expected_benchmark
    )

    assert set(
        dataset.metric_series
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert all(
        len(series.points) == 16
        for series
        in dataset.metric_series.values()
    )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_pre_change_history_is_strictly_before_change(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    _, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for series in (
        dataset.metric_series.values()
    ):
        pre_change = (
            series.points[:6]
        )

        assert all(
            point.timestamp
            < dataset.change_boundary_time
            for point in pre_change
        )

        assert all(
            point.operational_state
            == OperationalState.NORMAL
            for point in pre_change
        )

        assert all(
            point.perturbation_strength
            == 0.0
            for point in pre_change
        )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_incident_timestamps_are_strictly_increasing(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    _, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for series in (
        dataset.metric_series.values()
    ):
        timestamps = tuple(
            point.timestamp
            for point in series.points
        )

        assert all(
            current < following
            for current, following
            in itertools.pairwise(timestamps)
        )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_pre_change_telemetry_is_normal(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    _, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    for series in (
        dataset.metric_series.values()
    ):
        assert all(
            point.classification
            == MetricClassification.NORMAL
            for point in series.points[:6]
        )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_incident_metrics_degrade_in_metric_direction(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    runtime, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
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
            point
            for point in series.points
            if (
                point.perturbation_phase
                is not None
                and point.operational_state
                in {
                    OperationalState.OBSERVING,
                    OperationalState.DEGRADED,
                }
            )
        )

        values = tuple(
            point.observed_value
            for point in degradation
        )

        if (
            definition.direction
            == MetricDirection.LOWER_IS_BETTER
        ):
            assert all(
                current <= following
                for current, following
                in itertools.pairwise(values)
            )

        elif (
            definition.direction
            == MetricDirection.HIGHER_IS_BETTER
        ):
            assert all(
                current >= following
                for current, following
                in itertools.pairwise(values)
            )

        else:
            pytest.fail(
                "Context-dependent Metric appeared "
                "in standard incident history."
            )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_peak_incident_matches_resolved_blocking_thresholds(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    runtime, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
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
            point.observed_value
            == pytest.approx(
                benchmark.blocking_threshold
            )
            for point in peak_points
        )

        assert all(
            point.classification
            == MetricClassification.BLOCKING
            for point in peak_points
        )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_recovery_moves_metrics_back_toward_normal(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    runtime, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
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

        recovery = tuple(
            point
            for point in series.points
            if (
                point.operational_state
                == OperationalState.RECOVERY
            )
        )

        values = tuple(
            point.observed_value
            for point in recovery
        )

        if (
            definition.direction
            == MetricDirection.LOWER_IS_BETTER
        ):
            assert all(
                current >= following
                for current, following
                in itertools.pairwise(values)
            )

        elif (
            definition.direction
            == MetricDirection.HIGHER_IS_BETTER
        ):
            assert all(
                current <= following
                for current, following
                in itertools.pairwise(values)
            )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_recovery_finishes_at_healthy_counterfactual(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    _, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
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
            final_point.observed_value
            == pytest.approx(
                final_point
                .counterfactual_value
            )
        )

        assert (
            final_point.classification
            == MetricClassification.NORMAL
        )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
        "expected_scenario",
        "expected_service",
        "expected_baseline",
        "expected_benchmark",
    ),
    CASES,
)
def test_metrics_share_identical_incident_coordinates(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    _, dataset = build_case(
        scenario_path=scenario_path,
        enterprise_path=enterprise_path,
    )

    coordinates = []

    for series in (
        dataset.metric_series.values()
    ):
        coordinates.append(
            tuple(
                (
                    point.timestamp,
                    point.operational_state,
                    point.perturbation_phase,
                    point.perturbation_strength,
                )
                for point in series.points
            )
        )

    assert all(
        coordinate_set
        == coordinates[0]
        for coordinate_set
        in coordinates[1:]
    )
