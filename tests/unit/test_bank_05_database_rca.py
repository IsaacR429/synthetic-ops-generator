from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import (
    ScenarioFamily,
    SourceDomain,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"
SCENARIO_PATH = (
    CONFIG_ROOT
    / "scenarios"
    / "banking"
    / "BANK-05.yaml"
)
ENTERPRISE_PATH = (
    CONFIG_ROOT
    / "enterprises"
    / "bank_alpha"
)


def load_bank_05():
    return load_scenario(SCENARIO_PATH)


def load_bank_alpha():
    return load_enterprise_configuration(
        ENTERPRISE_PATH
    )


def test_bank_05_declares_database_rca_contract() -> None:
    scenario = load_bank_05()

    assert scenario.scenario_id == "BANK-05"
    assert (
        scenario.family
        == ScenarioFamily.ROOT_CAUSE_ANALYSIS
    )

    assert scenario.correlation.change_required is False

    assert (
        scenario.target.enterprise_id
        == "bank_alpha"
    )
    assert (
        scenario.target.business_stream_id
        == "payments"
    )
    assert (
        scenario.target.service_id
        == "payment_service"
    )
    assert (
        scenario.target.environment
        == Environment.PRODUCTION
    )

    assert len(scenario.behaviours) == 10

    assert (
        scenario.expected_result.expected_root_cause
        == "account_database"
    )

    assert (
        scenario.expected_result.expected_incident_attribution
        is False
    )


def test_bank_05_execution_plan_resolves_rca_targets() -> None:
    scenario = load_bank_05()
    enterprise = load_bank_alpha()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    assert len(plan.entries) == len(
        scenario.behaviours
    )

    assert [
        entry.behaviour
        for entry in plan.entries
    ] == scenario.behaviours

    targeted_entries = [
        entry
        for entry in plan.entries
        if entry.execution_target is not None
    ]

    assert len(targeted_entries) == 4

    actual_targets = [
        (
            entry.behaviour.source,
            entry.behaviour.profile_id,
            entry.execution_target.business_stream,
            entry.execution_target.service,
            entry.execution_target.component,
            entry.execution_target.environment,
        )
        for entry in targeted_entries
    ]

    assert actual_targets == [
        (
            SourceDomain.INFRASTRUCTURE_TEST,
            "required_check_failed",
            "core_banking",
            "account_service",
            "account_database",
            Environment.PRODUCTION,
        ),
        (
            SourceDomain.LOG,
            "degradation_error_logs",
            "core_banking",
            "account_service",
            "account_api",
            Environment.PRODUCTION,
        ),
        (
            SourceDomain.INFRASTRUCTURE_TEST,
            "all_required_checks_pass",
            "core_banking",
            "account_service",
            "account_database",
            Environment.PRODUCTION,
        ),
        (
            SourceDomain.LOG,
            "recovery_operational_logs",
            "core_banking",
            "account_service",
            "account_api",
            Environment.PRODUCTION,
        ),
    ]


def test_bank_05_builds_all_execution_bindings() -> None:
    scenario = load_bank_05()
    enterprise = load_bank_alpha()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    factory = GeneratorFactory(
        config_root=CONFIG_ROOT
    )

    bindings = factory.build_execution_bindings(
        scenario=scenario,
        enterprise=enterprise,
        plan=plan,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    assert len(bindings) == 10

    assert [
        binding.behaviour
        for binding in bindings
    ] == scenario.behaviours

    assert [
        binding.execution_target
        for binding in bindings
    ] == [
        entry.execution_target
        for entry in plan.entries
    ]

    assert [
        binding.generator.__class__.__name__
        for binding in bindings
    ] == [
        "MetricGenerator",
        "MetricGenerator",
        "InfrastructureTestGenerator",
        "LogGenerator",
        "MetricGenerator",
        "LogGenerator",
        "InfrastructureTestGenerator",
        "LogGenerator",
        "MetricGenerator",
        "LogGenerator",
    ]

    targeted_bindings = [
        binding
        for binding in bindings
        if binding.execution_target is not None
    ]

    assert {
        (
            binding.execution_target.service,
            binding.execution_target.component,
        )
        for binding in targeted_bindings
    } == {
        (
            "account_service",
            "account_database",
        ),
        (
            "account_service",
            "account_api",
        ),
    }
