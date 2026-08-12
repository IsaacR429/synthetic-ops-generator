import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkCatalogue,
)
from synthetic_ops_generator.benchmarks.resolver import (
    resolve_benchmark,
)
from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestGenerator,
)
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.generators.log import LogGenerator
from synthetic_ops_generator.generators.manual_validation import (
    ManualValidationGenerator,
)
from synthetic_ops_generator.generators.metric import (
    MetricGenerator,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
)
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)

SCENARIO_ROOT = Path("config/scenarios")
ENTERPRISE_ROOT = Path("config/enterprises")


def find_scenario_path(
    scenario_id: str,
) -> Path:
    matches = list(
        SCENARIO_ROOT.rglob(
            f"{scenario_id}.yaml"
        )
    )

    if not matches:
        raise FileNotFoundError(
            f"Scenario configuration not found: "
            f"{scenario_id}"
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple Scenario configurations found "
            f"for {scenario_id}."
        )

    return matches[0]


def find_service(
    scenario: ScenarioDefinition,
    enterprise,
):
    return next(
        service
        for service in enterprise.services
        if service.service_id
        == scenario.target.service_id
    )


def build_supported_generators(
    *,
    scenario: ScenarioDefinition,
    enterprise,
    ids: IdFactory,
    random_source: SimulationRandom,
) -> list[SourceGenerator]:
    generators: list[SourceGenerator] = []

    service = find_service(
        scenario,
        enterprise,
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
            "config/metrics/definitions.yaml",
            MetricCatalogue,
        )

        benchmark_catalogue = load_yaml_model(
            "config/benchmarks/synthetic_defaults.yaml",
            BenchmarkCatalogue,
        )

        baseline_profile = load_yaml_model(
            "config/baselines/synthetic_defaults.yaml",
            BaselineProfile,
        )

        if (
            baseline_profile.profile_id
            != service.baseline_profile_id
        ):
            raise ValueError(
                "Configured Baseline profile does not match "
                f"Service {service.service_id}: "
                f"{service.baseline_profile_id}"
            )

        benchmark_profile = (
            benchmark_catalogue.profiles.get(
                service.benchmark_profile_id
            )
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
                    "Baseline references unknown Metric Definition: "
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

            resolved_benchmarks[metric_id] = (
                resolve_benchmark(
                    definition,
                    base_policy,
                )
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
                    component_ids=(
                        scenario.target.component_ids
                    ),
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
                    baseline_profile=(
                        metric_baseline_profile
                    ),
                    benchmarks=(
                        resolved_metric_benchmarks
                    ),
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

        elif (
            behaviour.source
            == SourceDomain.DEPLOYMENT
        ):
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
                    artifact_version=(
                        scenario.trigger.version
                    ),
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

    return generators


async def run(
    scenario_id: str,
) -> None:
    scenario_path = find_scenario_path(
        scenario_id
    )

    scenario = load_scenario(
        scenario_path
    )

    enterprise_path = (
        ENTERPRISE_ROOT
        / scenario.target.enterprise_id
    )

    enterprise = load_enterprise_configuration(
        enterprise_path
    )

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )

    ids = IdFactory()

    clock = ManualSimulationClock(
        datetime.now(UTC)
    )

    runner = ScenarioRunner(
        ids=ids,
        clock=clock,
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    random_source = SimulationRandom(
        context.random_seed
    )

    publisher = InMemoryPublisher()

    generators = build_supported_generators(
        scenario=scenario,
        enterprise=enterprise,
        ids=ids,
        random_source=random_source,
    )

    visited_states = await runner.execute(
        scenario=scenario,
        context=context,
        generators=generators,
        publisher=publisher,
        event_interval_seconds=5,
    )

    print()
    print(
        f"Scenario: {scenario.scenario_id} "
        f"- {scenario.name}"
    )
    print(
        f"Enterprise: "
        f"{enterprise.enterprise_id}"
    )
    print(
        f"Business Stream: "
        f"{context.business_stream}"
    )
    print(
        f"Service: {context.service}"
    )
    print(
        f"Run: {context.run_id}"
    )
    print(
        f"Change: {context.chg_id}"
    )

    if context.deployment_id:
        print(
            f"Deployment: "
            f"{context.deployment_id}"
        )

    print()
    print(
        "State Plan: "
        + " -> ".join(visited_states)
    )

    print()
    print("Generated Source Events:")

    for event in publisher.events:
        print(
            f"{event.sequence_number:02d} | "
            f"{event.event_time.isoformat()} | "
            f"{event.event_type} | "
            f"{event.source_system}"
        )

    print()
    print(
        f"Events Generated: "
        f"{len(publisher.events)}"
    )

    print(
        "Supported Sources Executed: "
        "ITSM, Metric, Infrastructure Test, "
        "Deployment, Application Test, Log"
    )

    print()
    print(
        "Expected Test Oracle "
        "(not generated source data):"
    )

    print(
        f"Decision: "
        f"{scenario.expected_result.expected_decision}"
    )

    print(
        f"Action: "
        f"{scenario.expected_result.expected_action}"
    )

    print(
        f"Outcome: "
        f"{scenario.expected_result.expected_outcome}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Execute a configured synthetic "
            "operational Scenario."
        )
    )

    parser.add_argument(
        "scenario_id",
        help="Scenario ID, for example BANK-01",
    )

    args = parser.parse_args()

    asyncio.run(
        run(args.scenario_id)
    )


if __name__ == "__main__":
    main()