from collections.abc import Iterator

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.history.healthy_change_dataset import (
    HistoricalHealthyChangeDataset,
)
from synthetic_ops_generator.history.incident_dataset import (
    HistoricalIncidentDataset,
)
from synthetic_ops_generator.history.scenario_runtime import (
    HistoricalScenarioRuntime,
)
from synthetic_ops_generator.metrics.event_payload import (
    METRIC_EVENT_TYPE,
    METRIC_SOURCE_SYSTEM,
    MetricHistoricalContext,
    build_metric_event_data,
)
from synthetic_ops_generator.scenarios.context import ScenarioContext


def build_historical_metric_events(
    *,
    dataset: HistoricalIncidentDataset,
    runtime: HistoricalScenarioRuntime,
    context: ScenarioContext,
    ids: IdFactory,
) -> tuple[GeneratedEvent, ...]:
    return tuple(
        iter_historical_metric_events(
            dataset=dataset,
            runtime=runtime,
            context=context,
            ids=ids,
        )
    )


def iter_historical_metric_events(
    *,
    dataset: HistoricalIncidentDataset,
    runtime: HistoricalScenarioRuntime,
    context: ScenarioContext,
    ids: IdFactory,
) -> Iterator[GeneratedEvent]:
    _validate_event_adapter_inputs(
        dataset=dataset,
        runtime=runtime,
        context=context,
    )

    baseline_profile = (
        runtime.metric_runtime.baseline_profile
    )
    metric_runtime = runtime.metric_runtime

    first_metric = next(
        iter(dataset.metric_series.values())
    )
    point_count = len(first_metric.points)

    for point_index in range(point_count):
        for metric_id in sorted(
            dataset.metric_series.keys()
        ):
            series = dataset.metric_series[metric_id]
            point = series.points[point_index]

            definition = metric_runtime.definitions[metric_id]
            baseline = baseline_profile.metrics[metric_id]
            benchmark = metric_runtime.resolved_benchmarks[metric_id]

            historical_context = MetricHistoricalContext(
                counterfactual_value=point.counterfactual_value,
                perturbation_strength=point.perturbation_strength,
                perturbation_phase=(
                    point.perturbation_phase.value
                    if point.perturbation_phase is not None
                    else None
                ),
            )

            event_data = build_metric_event_data(
                definition=definition,
                baseline=baseline,
                benchmark=benchmark,
                baseline_profile_id=dataset.baseline_profile_id,
                benchmark_profile_id=dataset.benchmark_profile_id,
                behaviour_profile_id=None,
                scenario_state=point.operational_state,
                observed_value=point.observed_value,
                classification=point.classification,
                historical_context=historical_context,
            )

            yield GeneratedEvent(
                event_id=ids.event_id(),
                event_type=METRIC_EVENT_TYPE,
                event_time=point.timestamp,
                source_system=METRIC_SOURCE_SYSTEM,
                source_domain=SourceDomain.METRIC,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=None,
                environment=context.environment,
                sequence_number=context.next_sequence(),
                data=event_data,
            )


def _validate_event_adapter_inputs(
    *,
    dataset: HistoricalIncidentDataset,
    runtime: HistoricalScenarioRuntime,
    context: ScenarioContext,
) -> None:
    if not dataset.metric_series:
        raise ValueError(
            "Historical dataset contains "
            "no Metric series."
        )

    if (
        dataset.scenario_id
        != runtime.scenario.scenario_id
    ):
        raise ValueError(
            "Historical dataset Scenario "
            "does not match runtime."
        )

    if (
        dataset.enterprise_id
        != runtime.enterprise.enterprise_id
    ):
        raise ValueError(
            "Historical dataset Enterprise "
            "does not match runtime."
        )

    if (
        dataset.service_id
        != runtime.service.service_id
    ):
        raise ValueError(
            "Historical dataset Service "
            "does not match runtime."
        )

    if (
        dataset.baseline_profile_id
        != runtime.metric_runtime
        .baseline_profile.profile_id
    ):
        raise ValueError(
            "Historical dataset Baseline "
            "does not match runtime."
        )

    if (
        dataset.benchmark_profile_id
        != runtime.metric_runtime
        .benchmark_profile_id
    ):
        raise ValueError(
            "Historical dataset Benchmark "
            "does not match runtime."
        )

    if (
        context.scenario_id
        != dataset.scenario_id
    ):
        raise ValueError(
            "ScenarioContext does not match "
            "historical dataset Scenario."
        )

    if (
        context.service
        != dataset.service_id
    ):
        raise ValueError(
            "ScenarioContext does not match "
            "historical dataset Service."
        )

    if (
        context.business_stream
        != runtime.scenario
        .target.business_stream_id
    ):
        raise ValueError(
            "ScenarioContext Business Stream "
            "does not match runtime."
        )

    expected_metrics = set(
        runtime.metric_runtime
        .baseline_profile.metrics
    )

    if (
        set(dataset.metric_series)
        != expected_metrics
    ):
        raise ValueError(
            "Historical dataset Metric coverage "
            "does not match runtime configuration."
        )


def build_historical_healthy_metric_events(
    *,
    dataset: HistoricalHealthyChangeDataset,
    runtime: HistoricalScenarioRuntime,
    context: ScenarioContext,
    ids: IdFactory,
) -> tuple[GeneratedEvent, ...]:
    return tuple(
        iter_historical_healthy_metric_events(
            dataset=dataset,
            runtime=runtime,
            context=context,
            ids=ids,
        )
    )


def iter_historical_healthy_metric_events(
    *,
    dataset: HistoricalHealthyChangeDataset,
    runtime: HistoricalScenarioRuntime,
    context: ScenarioContext,
    ids: IdFactory,
) -> Iterator[GeneratedEvent]:
    _validate_healthy_event_adapter_inputs(
        dataset=dataset,
        runtime=runtime,
        context=context,
    )

    baseline_profile = (
        runtime.metric_runtime.baseline_profile
    )
    metric_runtime = runtime.metric_runtime

    first_metric = next(
        iter(dataset.metric_series.values())
    )
    point_count = len(first_metric.points)

    for point_index in range(point_count):
        for metric_id in sorted(
            dataset.metric_series.keys()
        ):
            series = dataset.metric_series[metric_id]
            point = series.points[point_index]

            definition = metric_runtime.definitions[metric_id]
            baseline = baseline_profile.metrics[metric_id]
            benchmark = metric_runtime.resolved_benchmarks[metric_id]

            historical_context = MetricHistoricalContext(
                counterfactual_value=point.counterfactual_value,
                perturbation_strength=0.0,
                perturbation_phase=None,
            )

            event_data = build_metric_event_data(
                definition=definition,
                baseline=baseline,
                benchmark=benchmark,
                baseline_profile_id=dataset.baseline_profile_id,
                benchmark_profile_id=dataset.benchmark_profile_id,
                behaviour_profile_id=None,
                scenario_state=point.operational_state,
                observed_value=point.observed_value,
                classification=point.classification,
                historical_context=historical_context,
            )

            yield GeneratedEvent(
                event_id=ids.event_id(),
                event_type=METRIC_EVENT_TYPE,
                event_time=point.timestamp,
                source_system=METRIC_SOURCE_SYSTEM,
                source_domain=SourceDomain.METRIC,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=None,
                environment=context.environment,
                sequence_number=context.next_sequence(),
                data=event_data,
            )


def _validate_healthy_event_adapter_inputs(
    *,
    dataset: HistoricalHealthyChangeDataset,
    runtime: HistoricalScenarioRuntime,
    context: ScenarioContext,
) -> None:
    if not dataset.metric_series:
        raise ValueError(
            "Historical healthy dataset contains "
            "no Metric series."
        )

    if (
        dataset.scenario_id
        != runtime.scenario.scenario_id
    ):
        raise ValueError(
            "Historical dataset Scenario "
            "does not match runtime."
        )

    if (
        dataset.enterprise_id
        != runtime.enterprise.enterprise_id
    ):
        raise ValueError(
            "Historical dataset Enterprise "
            "does not match runtime."
        )

    if (
        dataset.service_id
        != runtime.service.service_id
    ):
        raise ValueError(
            "Historical dataset Service "
            "does not match runtime."
        )

    if (
        dataset.baseline_profile_id
        != runtime.metric_runtime
        .baseline_profile.profile_id
    ):
        raise ValueError(
            "Historical dataset Baseline "
            "does not match runtime."
        )

    if (
        dataset.benchmark_profile_id
        != runtime.metric_runtime
        .benchmark_profile_id
    ):
        raise ValueError(
            "Historical dataset Benchmark "
            "does not match runtime."
        )

    if (
        context.scenario_id
        != dataset.scenario_id
    ):
        raise ValueError(
            "ScenarioContext does not match "
            "historical dataset Scenario."
        )

    if (
        context.service
        != dataset.service_id
    ):
        raise ValueError(
            "ScenarioContext does not match "
            "historical dataset Service."
        )

    if (
        context.business_stream
        != runtime.scenario
        .target.business_stream_id
    ):
        raise ValueError(
            "ScenarioContext Business Stream "
            "does not match runtime."
        )

    expected_metrics = set(
        runtime.metric_runtime
        .baseline_profile.metrics
    )

    if (
        set(dataset.metric_series)
        != expected_metrics
    ):
        raise ValueError(
            "Historical dataset Metric coverage "
            "does not match runtime configuration."
        )
