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
    build_historical_incident_dataset,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
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

CONFIG_ROOT = Path("config")


def build_dataset(
    *,
    scenario_path: Path,
    enterprise_path: Path,
    seed: int = 42,
):
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
        "expected_scenario",
        "expected_service",
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
            "BANK-02",
            "payment_service",
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
        ),
    ],
)
def test_builds_real_historical_incident_dataset(
    scenario_path: Path,
    enterprise_path: Path,
    expected_scenario: str,
    expected_service: str,
) -> None:
    dataset = build_dataset(
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


def test_incident_dataset_contains_complete_timeline(
) -> None:
    dataset = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    assert all(
        len(series.points) == 16
        for series
        in dataset.metric_series.values()
    )


def test_incident_dataset_preserves_change_and_rollback_boundaries(
) -> None:
    dataset = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    assert (
        dataset.change_boundary_time
        == datetime(
            2026,
            8,
            14,
            10,
            0,
            tzinfo=UTC,
        )
    )

    assert (
        dataset.rollback_boundary_time
        == datetime(
            2026,
            8,
            14,
            10,
            30,
            tzinfo=UTC,
        )
    )

    assert all(
        point.timestamp
        != dataset.change_boundary_time
        for series
        in dataset.metric_series.values()
        for point in series.points
    )


def test_all_metrics_share_identical_incident_timestamps(
) -> None:
    dataset = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    timelines = [
        tuple(
            point.timestamp
            for point in series.points
        )
        for series
        in dataset.metric_series.values()
    ]

    assert all(
        timeline == timelines[0]
        for timeline in timelines[1:]
    )


def test_incident_dataset_contains_expected_operational_states(
) -> None:
    dataset = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
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

    assert states[6:9] == (
        OperationalState.OBSERVING,
    ) * 3

    assert states[9:12] == (
        OperationalState.DEGRADED,
    ) * 3

    assert states[12:] == (
        OperationalState.RECOVERY,
    ) * 4


def test_peak_incident_points_are_blocking(
) -> None:
    dataset = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
    )

    for series in (
        dataset.metric_series.values()
    ):
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


def test_final_recovery_returns_all_metrics_to_normal(
) -> None:
    dataset = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
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
            final_point
            .perturbation_strength
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


def test_incident_dataset_is_reproducible_for_same_seed(
) -> None:
    kwargs = {
        "scenario_path": Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        "enterprise_path": Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        "seed": 42,
    }

    assert (
        build_dataset(**kwargs)
        == build_dataset(**kwargs)
    )


def test_incident_dataset_varies_for_different_seed(
) -> None:
    first = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        seed=42,
    )

    second = build_dataset(
        scenario_path=Path(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
        enterprise_path=Path(
            "config/enterprises/"
            "bank_alpha"
        ),
        seed=43,
    )

    assert first != second
