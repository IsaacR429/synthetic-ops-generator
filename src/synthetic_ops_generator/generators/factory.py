from collections.abc import Sequence
from pathlib import Path

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkCatalogue,
)
from synthetic_ops_generator.benchmarks.resolver import (
    resolve_benchmark,
)
from synthetic_ops_generator.config.loader import load_yaml_model
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
    Service,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestGenerator,
)
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.generators.evidence import (
    EvidenceGenerator,
)
from synthetic_ops_generator.generators.incident import (
    IncidentGenerator,
)
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.generators.log import LogGenerator
from synthetic_ops_generator.generators.manual_validation import (
    ManualValidationGenerator,
)
from synthetic_ops_generator.generators.metric import MetricGenerator
from synthetic_ops_generator.metrics.models import MetricCatalogue
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
    SourceDomain,
)


class GeneratorFactory:
    """
    Builds source generators required by a Scenario definition.

    Runtime configuration paths are resolved from a supplied
    configuration root so CLI and API execution can share the
    same generator construction logic.
    """

    def __init__(
        self,
        *,
        config_root: str | Path,
    ) -> None:
        self._config_root = Path(config_root)

    def build(
        self,
        *,
        scenario: ScenarioDefinition,
        enterprise: Enterprise,
        ids: IdFactory,
        random_source: SimulationRandom,
        event_history: Sequence[GeneratedEvent],
    ) -> list[SourceGenerator]:
        generators: list[SourceGenerator] = []

        service = self._find_service(
            scenario=scenario,
            enterprise=enterprise,
        )

        metric_definitions = None
        metric_baseline_profile = None
        resolved_metric_benchmarks = None
        metric_benchmark_profile_id = None

        has_metric_behaviour = any(
            behaviour.source == SourceDomain.METRIC
            for behaviour in scenario.behaviours
        )

        if has_metric_behaviour:
            if service.benchmark_profile_id is None:
                raise ValueError(
                    f"Service {service.service_id} does not define "
                    "a Benchmark profile."
                )

            if service.baseline_profile_id is None:
                raise ValueError(
                    f"Service {service.service_id} does not define "
                    "a Baseline profile."
                )

            metric_catalogue = load_yaml_model(
                self._config_root
                / "metrics"
                / "definitions.yaml",
                MetricCatalogue,
            )

            benchmark_catalogue = load_yaml_model(
                self._config_root
                / "benchmarks"
                / "synthetic_defaults.yaml",
                BenchmarkCatalogue,
            )

            baseline_profile = load_baseline_profile(
                service.baseline_profile_id,
                directory=self._config_root / "baselines",
            )

            benchmark_profile = benchmark_catalogue.profiles.get(
                service.benchmark_profile_id
            )

            if benchmark_profile is None:
                raise ValueError(
                    "Configured Benchmark profile was not found: "
                    f"{service.benchmark_profile_id}"
                )

            resolved_benchmarks = {}

            for metric_id in baseline_profile.metrics:
                definition = metric_catalogue.definitions.get(
                    metric_id
                )

                if definition is None:
                    raise ValueError(
                        "Baseline references unknown "
                        "Metric Definition: "
                        f"{metric_id}"
                    )

                base_policy = benchmark_profile.metrics.get(
                    metric_id
                )

                if base_policy is None:
                    raise ValueError(
                        "Benchmark profile does not define Metric: "
                        f"{metric_id}"
                    )

                resolved_benchmarks[metric_id] = resolve_benchmark(
                    definition,
                    base_policy,
                )

            metric_definitions = metric_catalogue.definitions
            metric_baseline_profile = baseline_profile
            resolved_metric_benchmarks = resolved_benchmarks
            metric_benchmark_profile_id = (
                benchmark_profile.profile_id
            )

        for behaviour in scenario.behaviours:
            if behaviour.source == SourceDomain.ITSM:
                generators.append(
                    ITSMGenerator(
                        ids=ids,
                        behaviour=behaviour,
                        service_owner=service.owner,
                        component_ids=scenario.target.component_ids,
                    )
                )

            elif behaviour.source == SourceDomain.METRIC:
                if (
                    metric_definitions is None
                    or metric_baseline_profile is None
                    or resolved_metric_benchmarks is None
                    or metric_benchmark_profile_id is None
                ):
                    raise RuntimeError(
                        "Metric runtime configuration "
                        "was not resolved."
                    )

                generators.append(
                    MetricGenerator(
                        ids=ids,
                        behaviour=behaviour,
                        definitions=metric_definitions,
                        baseline_profile=metric_baseline_profile,
                        benchmarks=resolved_metric_benchmarks,
                        benchmark_profile_id=(
                            metric_benchmark_profile_id
                        ),
                        random_source=random_source,
                    )
                )

            elif (
                behaviour.source
                == SourceDomain.INFRASTRUCTURE_TEST
            ):
                generators.append(
                    InfrastructureTestGenerator(
                        ids=ids,
                        behaviour=behaviour,
                    )
                )

            elif behaviour.source == SourceDomain.DEPLOYMENT:
                if scenario.trigger.artifact is None:
                    raise ValueError(
                        "Deployment behaviour requires "
                        "a trigger artifact."
                    )

                if scenario.trigger.version is None:
                    raise ValueError(
                        "Deployment behaviour requires "
                        "a trigger artifact version."
                    )

                generators.append(
                    DeploymentGenerator(
                        ids=ids,
                        behaviour=behaviour,
                        artifact=scenario.trigger.artifact,
                        artifact_version=scenario.trigger.version,
                    )
                )

            elif (
                behaviour.source
                == SourceDomain.APPLICATION_TEST
            ):
                generators.append(
                    ApplicationTestGenerator(
                        ids=ids,
                        behaviour=behaviour,
                    )
                )

            elif behaviour.source == SourceDomain.LOG:
                generators.append(
                    LogGenerator(
                        ids=ids,
                        behaviour=behaviour,
                    )
                )

            elif (
                behaviour.source
                == SourceDomain.MANUAL_VALIDATION
            ):
                generators.append(
                    ManualValidationGenerator(
                        ids=ids,
                        behaviour=behaviour,
                    )
                )

            elif behaviour.source == SourceDomain.INCIDENT:
                generators.append(
                    IncidentGenerator(
                        ids=ids,
                        behaviour=behaviour,
                        event_history=event_history,
                    )
                )

            elif behaviour.source == SourceDomain.EVIDENCE:
                generators.append(
                    EvidenceGenerator(
                        ids=ids,
                        behaviour=behaviour,
                        event_history=event_history,
                    )
                )

        return generators

    @staticmethod
    def _find_service(
        *,
        scenario: ScenarioDefinition,
        enterprise: Enterprise,
    ) -> Service:
        for service in enterprise.services:
            if service.service_id == scenario.target.service_id:
                return service

        raise ValueError(
            "Scenario target Service was not found in Enterprise: "
            f"{scenario.target.service_id}"
        )