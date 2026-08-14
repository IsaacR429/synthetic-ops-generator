from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.scenarios.loader import load_scenario

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


def test_generator_factory_builds_bank_01_generators() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )

    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )

    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    assert len(generators) == len(
        scenario.behaviours
    )


def test_generator_factory_preserves_scenario_order() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )

    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )

    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    assert len(generators) == 9

    assert [
        generator.__class__.__name__
        for generator in generators
    ] == [
        "ITSMGenerator",
        "MetricGenerator",
        "InfrastructureTestGenerator",
        "DeploymentGenerator",
        "ApplicationTestGenerator",
        "MetricGenerator",
        "LogGenerator",
        "IncidentGenerator",
        "EvidenceGenerator",
    ]


def test_generator_factory_builds_insurance_scenario() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "insurance"
        / "INS-01.yaml"
    )

    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "insurer_alpha"
    )

    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    assert len(generators) == len(
        scenario.behaviours
    )