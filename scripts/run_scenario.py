import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
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
) -> list[SourceGenerator]:
    generators: list[SourceGenerator] = []

    service = find_service(
        scenario,
        enterprise,
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

    publisher = InMemoryPublisher()

    generators = build_supported_generators(
        scenario=scenario,
        enterprise=enterprise,
        ids=ids,
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
        "ITSM, Deployment"
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