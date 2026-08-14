from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.benchmarks.evaluator import (
    classify_metric,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.history.observations import (
    build_historical_observations,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
    PerturbationPhase,
    anchor_perturbation_curve,
    build_metric_perturbation_series,
    build_perturbation_curve,
)
from synthetic_ops_generator.history.scenario_alignment import (
    align_rollback_perturbation,
)
from synthetic_ops_generator.history.scenario_runtime import (
    HistoricalScenarioRuntime,
)
from synthetic_ops_generator.history.series import (
    build_historical_expectations,
)
from synthetic_ops_generator.history.timeline import (
    build_baseline_timeline,
)
from synthetic_ops_generator.metrics.models import (
    MetricClassification,
)


@dataclass(frozen=True)
class HistoricalIncidentMetricPoint:
    timestamp: datetime

    operational_state: OperationalState

    perturbation_phase: (
        PerturbationPhase | None
    )

    perturbation_strength: float

    counterfactual_value: float
    observed_value: float

    classification: MetricClassification


@dataclass(frozen=True)
class HistoricalIncidentMetricSeries:
    metric_definition_id: str

    points: tuple[
        HistoricalIncidentMetricPoint,
        ...,
    ]


@dataclass(frozen=True)
class HistoricalIncidentDataset:
    scenario_id: str
    enterprise_id: str
    service_id: str

    baseline_profile_id: str
    benchmark_profile_id: str

    change_boundary_time: datetime
    rollback_boundary_time: datetime

    sample_interval_seconds: int

    metric_series: dict[
        str,
        HistoricalIncidentMetricSeries,
    ]


def build_historical_incident_dataset(
    *,
    runtime: HistoricalScenarioRuntime,
    anchor_time: datetime,
    curve_spec: PerturbationCurveSpec,
    random_source: SimulationRandom,
) -> HistoricalIncidentDataset:
    baseline_profile = (
        runtime.metric_runtime.baseline_profile
    )
    metric_runtime = runtime.metric_runtime

    timeline = build_baseline_timeline(
        end_time=anchor_time,
        baseline_profile=baseline_profile,
    )

    expectations = build_historical_expectations(
        timeline=timeline,
        baseline_profile=baseline_profile,
        runtime_profile=(
            runtime.historical_runtime_profile
        ),
        random_source=random_source,
    )

    observations = build_historical_observations(
        baseline_profile=baseline_profile,
        expectation_bundle=expectations,
        random_source=random_source,
    )

    curve = build_perturbation_curve(
        spec=curve_spec
    )

    perturbation_timeline = anchor_perturbation_curve(
        curve=curve,
        anchor_time=anchor_time,
        sample_interval_seconds=(
            baseline_profile.sample_interval_seconds
        ),
    )

    alignment = align_rollback_perturbation(
        scenario=runtime.scenario,
        timeline=perturbation_timeline,
    )

    metric_series: dict[
        str,
        HistoricalIncidentMetricSeries,
    ] = {}

    for metric_id in sorted(
        baseline_profile.metrics
    ):
        definition = (
            metric_runtime.definitions[metric_id]
        )
        benchmark = (
            metric_runtime.resolved_benchmarks[
                metric_id
            ]
        )
        healthy_obs = (
            observations.metric_series[metric_id]
        )

        healthy_reference = (
            healthy_obs.points[-1].observed_value
        )

        perturbation_series = (
            build_metric_perturbation_series(
                definition=definition,
                benchmark=benchmark,
                healthy_value=healthy_reference,
                curve=curve,
            )
        )

        points: list[
            HistoricalIncidentMetricPoint
        ] = []

        for obs_point in healthy_obs.points:
            classification = classify_metric(
                definition,
                benchmark,
                obs_point.observed_value,
            )

            points.append(
                HistoricalIncidentMetricPoint(
                    timestamp=(
                        obs_point.timestamp
                    ),
                    operational_state=(
                        OperationalState.NORMAL
                    ),
                    perturbation_phase=None,
                    perturbation_strength=0.0,
                    counterfactual_value=(
                        obs_point.expected_value
                    ),
                    observed_value=(
                        obs_point.observed_value
                    ),
                    classification=(
                        classification
                    ),
                )
            )

        for (
            aligned_point,
            perturbation_point,
        ) in zip(
            alignment.points,
            perturbation_series.points,
            strict=True,
        ):
            if (
                aligned_point.sample_index
                != perturbation_point.sample_index
            ):
                raise RuntimeError(
                    "Scenario alignment and Metric "
                    "perturbation sample indices "
                    "do not match."
                )

            points.append(
                HistoricalIncidentMetricPoint(
                    timestamp=(
                        aligned_point.timestamp
                    ),
                    operational_state=(
                        aligned_point
                        .operational_state
                    ),
                    perturbation_phase=(
                        aligned_point.phase
                    ),
                    perturbation_strength=(
                        aligned_point.strength
                    ),
                    counterfactual_value=(
                        healthy_reference
                    ),
                    observed_value=(
                        perturbation_point
                        .perturbed_value
                    ),
                    classification=(
                        perturbation_point
                        .classification
                    ),
                )
            )

        metric_series[
            metric_id
        ] = HistoricalIncidentMetricSeries(
            metric_definition_id=metric_id,
            points=tuple(points),
        )

    return HistoricalIncidentDataset(
        scenario_id=(
            runtime.scenario.scenario_id
        ),
        enterprise_id=(
            runtime.enterprise.enterprise_id
        ),
        service_id=(
            runtime.service.service_id
        ),
        baseline_profile_id=(
            baseline_profile.profile_id
        ),
        benchmark_profile_id=(
            metric_runtime
            .benchmark_profile_id
        ),
        change_boundary_time=(
            alignment.change_boundary_time
        ),
        rollback_boundary_time=(
            alignment.rollback_boundary_time
        ),
        sample_interval_seconds=(
            baseline_profile
            .sample_interval_seconds
        ),
        metric_series=metric_series,
    )
