from dataclasses import dataclass
from pathlib import Path

from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
    Service,
)
from synthetic_ops_generator.history.adapter import (
    HistoricalRuntimeProfile,
    build_historical_runtime_profile,
)
from synthetic_ops_generator.history.loader import (
    load_historical_behaviour_profile,
)
from synthetic_ops_generator.history.models import (
    HistoricalBehaviourProfile,
)
from synthetic_ops_generator.metrics.runtime import (
    MetricRuntimeConfiguration,
    resolve_metric_runtime_configuration,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
    SourceDomain,
)


@dataclass(frozen=True)
class HistoricalScenarioRuntime:
    scenario: ScenarioDefinition
    enterprise: Enterprise
    service: Service

    metric_runtime: MetricRuntimeConfiguration

    historical_profile: (
        HistoricalBehaviourProfile
    )

    historical_runtime_profile: (
        HistoricalRuntimeProfile
    )


def _resolve_historical_metric_ids(
    *,
    scenario: ScenarioDefinition,
    metric_runtime: MetricRuntimeConfiguration,
) -> tuple[str, ...]:
    metric_ids: list[str] = []
    for behaviour in scenario.behaviours:
        if behaviour.source != SourceDomain.METRIC:
            continue
        selection = behaviour.selection
        if (
            selection is None
            or selection.metric_ids is None
        ):
            metric_ids = list(
                metric_runtime
                .baseline_profile
                .metrics
            )
            break
        for metric_id in selection.metric_ids:
            if metric_id not in metric_ids:
                metric_ids.append(metric_id)

    for metric_id in metric_ids:
        if (
            metric_id
            not in metric_runtime.resolved_benchmarks
        ):
            raise ValueError(
                "Historical execution currently "
                "supports only benchmark-evaluable "
                f"Metrics. Unsupported: {metric_id}"
            )

    return tuple(metric_ids)


def _project_metric_runtime(
    *,
    metric_runtime: MetricRuntimeConfiguration,
    metric_ids: tuple[str, ...],
) -> MetricRuntimeConfiguration:
    projected_baseline_metrics = {
        metric_id: metric_runtime.baseline_profile.metrics[
            metric_id
        ]
        for metric_id in metric_ids
    }
    projected_baseline = (
        metric_runtime.baseline_profile.model_copy(
            update={"metrics": projected_baseline_metrics}
        )
    )
    projected_benchmarks = {
        metric_id: metric_runtime.resolved_benchmarks[
            metric_id
        ]
        for metric_id in metric_ids
        if metric_id in metric_runtime.resolved_benchmarks
    }
    return MetricRuntimeConfiguration(
        definitions=metric_runtime.definitions,
        baseline_profile=projected_baseline,
        resolved_benchmarks=projected_benchmarks,
        benchmark_profile_id=(
            metric_runtime.benchmark_profile_id
        ),
    )


def _project_historical_profile(
    *,
    historical_profile: HistoricalBehaviourProfile,
    metric_ids: tuple[str, ...],
) -> HistoricalBehaviourProfile:
    projected_responses = {
        metric_id: historical_profile.metric_responses[
            metric_id
        ]
        for metric_id in metric_ids
        if metric_id in historical_profile.metric_responses
    }
    return historical_profile.model_copy(
        update={"metric_responses": projected_responses}
    )


def build_historical_scenario_runtime(
    *,
    scenario: ScenarioDefinition,
    enterprise: Enterprise,
    config_root: str | Path,
) -> HistoricalScenarioRuntime:
    if (
        scenario.target.enterprise_id
        != enterprise.enterprise_id
    ):
        raise ValueError(
            "Scenario target Enterprise does not "
            "match the supplied Enterprise."
        )

    service = next(
        (
            service
            for service in enterprise.services
            if (
                service.service_id
                == scenario.target.service_id
            )
        ),
        None,
    )

    if service is None:
        raise ValueError(
            "Scenario target Service was not "
            "found in Enterprise: "
            f"{scenario.target.service_id}"
        )

    has_metric_behaviour = any(
        behaviour.source == SourceDomain.METRIC
        for behaviour in scenario.behaviours
    )

    if not has_metric_behaviour:
        raise ValueError(
            "Historical scenario runtime requires "
            "at least one Metric behaviour."
        )

    root = Path(config_root)

    metric_runtime = (
        resolve_metric_runtime_configuration(
            service=service,
            config_root=root,
        )
    )

    historical_metric_ids = (
        _resolve_historical_metric_ids(
            scenario=scenario,
            metric_runtime=metric_runtime,
        )
    )

    historical_profile = (
        load_historical_behaviour_profile(
            metric_runtime.baseline_profile.profile_id,
            directory=(
                root
                / "historical_profiles"
            ),
        )
    )

    metric_runtime = _project_metric_runtime(
        metric_runtime=metric_runtime,
        metric_ids=historical_metric_ids,
    )

    historical_profile = (
        _project_historical_profile(
            historical_profile=historical_profile,
            metric_ids=historical_metric_ids,
        )
    )

    historical_runtime_profile = (
        build_historical_runtime_profile(
            baseline_profile=(
                metric_runtime.baseline_profile
            ),
            historical_profile=(
                historical_profile
            ),
        )
    )

    return HistoricalScenarioRuntime(
        scenario=scenario,
        enterprise=enterprise,
        service=service,
        metric_runtime=metric_runtime,
        historical_profile=historical_profile,
        historical_runtime_profile=(
            historical_runtime_profile
        ),
    )
