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

    historical_profile = (
        load_historical_behaviour_profile(
            metric_runtime.baseline_profile.profile_id,
            directory=(
                root
                / "historical_profiles"
            ),
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
