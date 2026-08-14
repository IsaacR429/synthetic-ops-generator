from collections.abc import Sequence
from pathlib import Path

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
from synthetic_ops_generator.metrics.runtime import (
    MetricRuntimeConfiguration,
    resolve_metric_runtime_configuration,
)
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

        metric_runtime: (
            MetricRuntimeConfiguration | None
        ) = None

        has_metric_behaviour = any(
            behaviour.source == SourceDomain.METRIC
            for behaviour in scenario.behaviours
        )

        if has_metric_behaviour:
            metric_runtime = (
                resolve_metric_runtime_configuration(
                    service=service,
                    config_root=self._config_root,
                )
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
                if metric_runtime is None:
                    raise RuntimeError(
                        "Metric runtime configuration "
                        "was not resolved."
                    )

                generators.append(
                    MetricGenerator(
                        ids=ids,
                        behaviour=behaviour,
                        definitions=(
                            metric_runtime.definitions
                        ),
                        baseline_profile=(
                            metric_runtime.baseline_profile
                        ),
                        benchmarks=(
                            metric_runtime.resolved_benchmarks
                        ),
                        benchmark_profile_id=(
                            metric_runtime.benchmark_profile_id
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