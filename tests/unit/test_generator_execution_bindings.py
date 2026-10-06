from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.generators.log import LogGenerator
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import load_scenario

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


def test_execution_bindings_preserve_behaviour_order() -> None:
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-03.yaml"
    )
    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )
    bindings = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build_execution_bindings(
        scenario=scenario,
        enterprise=enterprise,
        plan=plan,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )
    assert len(bindings) == len(
        scenario.behaviours
    )
    assert [
        binding.behaviour
        for binding in bindings
    ] == scenario.behaviours
    assert all(
        binding.execution_target is None
        for binding in bindings
    )


def test_execution_binding_preserves_resolved_target() -> None:
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-03.yaml"
    )
    log_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.LOG
    )
    log_behaviour.execution_node_id = (
        "account_database"
    )
    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )
    bindings = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build_execution_bindings(
        scenario=scenario,
        enterprise=enterprise,
        plan=plan,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )
    binding = next(
        binding
        for binding in bindings
        if binding.behaviour == log_behaviour
    )
    assert isinstance(
        binding.generator,
        LogGenerator,
    )
    assert binding.execution_target is not None
    assert (
        binding.execution_target.business_stream
        == "core_banking"
    )
    assert (
        binding.execution_target.service
        == "account_service"
    )
    assert (
        binding.execution_target.component
        == "account_database"
    )
    assert (
        binding.execution_target.environment
        == Environment.PRODUCTION
    )


def test_execution_bindings_use_entry_target_for_metric_runtime() -> None:
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-03.yaml"
    )
    metric_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    )
    metric_behaviour.execution_node_id = (
        "account_database"
    )
    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )
    with pytest.raises(
        ValueError,
        match=(
            "Service account_service does not define "
            "a Baseline profile"
        ),
    ):
        GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build_execution_bindings(
            scenario=scenario,
            enterprise=enterprise,
            plan=plan,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
        )


def test_execution_bindings_reject_plan_behaviour_mismatch() -> None:
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-03.yaml"
    )
    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )
    mismatched_scenario = scenario.model_copy(
        update={
            "behaviours": list(
                reversed(scenario.behaviours)
            )
        }
    )
    with pytest.raises(
        ValueError,
        match="behaviour order",
    ):
        GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build_execution_bindings(
            scenario=mismatched_scenario,
            enterprise=enterprise,
            plan=plan,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
        )
