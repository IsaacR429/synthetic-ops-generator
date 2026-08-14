import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)

CONFIG_ROOT = Path("config")
SCENARIO_ROOT = CONFIG_ROOT / "scenarios"
ENTERPRISE_ROOT = CONFIG_ROOT / "enterprises"


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
            "Scenario configuration not found: "
            f"{scenario_id}"
        )

    if len(matches) > 1:
        raise RuntimeError(
            "Multiple Scenario configurations found "
            f"for {scenario_id}."
        )

    return matches[0]


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

    generator_factory = GeneratorFactory(
        config_root=CONFIG_ROOT
    )

    generators = generator_factory.build(
        scenario=scenario,
        enterprise=enterprise,
        ids=ids,
        random_source=random_source,
        event_history=runner.event_history,
    )

    visited_states = await runner.execute(
        scenario=scenario,
        context=context,
        generators=generators,
        publisher=publisher,
        event_interval_seconds=5,
    )

    validation_report = CrossSourceValidator().validate(
        events=runner.event_history,
        context=context,
        enterprise=enterprise,
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

    print()
    print("Cross-Source Validation:")

    if validation_report.is_valid:
        print("Status: PASS")
        print("Findings: 0")
    else:
        print("Status: FAIL")
        print(
            f"Findings: "
            f"{len(validation_report.findings)}"
        )

        for finding in validation_report.findings:
            print(
                f"- {finding.requirement_id} | "
                f"{finding.rule} | "
                f"{finding.message}"
            )

    print(
        "Configured Scenario Sources: "
        "ITSM, Metric, Infrastructure Test, "
        "Deployment, Application Test, Log, Incident, Evidence"
    )

    if not validation_report.is_valid:
        raise RuntimeError(
            "Generated Scenario Run failed "
            "cross-source validation."
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