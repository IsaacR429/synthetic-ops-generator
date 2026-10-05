from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.generators.factory import GeneratorFactory
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.scenarios.context import (
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.generators.log import LogGenerator
from synthetic_ops_generator.generators.metric import (
    MetricGenerator,
)
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import (
    ScenarioMetricSelection,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    CAPACITY_PRESSURE,
)

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


def test_generator_factory_passes_shared_random_source_to_log_generator() -> None:
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

    random_source = SimulationRandom(42)

    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=random_source,
        event_history=[],
    )

    log_generator = next(
        generator
        for generator in generators
        if isinstance(generator, LogGenerator)
    )

    assert log_generator._random is random_source


def test_generator_factory_passes_metric_selection() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )
    metric_behaviour_index = next(
        index
        for index, behaviour in enumerate(
            scenario.behaviours
        )
        if behaviour.source == SourceDomain.METRIC
    )
    behaviours = list(scenario.behaviours)
    behaviours[metric_behaviour_index] = (
        behaviours[metric_behaviour_index].model_copy(
            update={
                "selection": ScenarioMetricSelection(
                    metric_ids=[
                        "request_latency",
                        "error_rate",
                    ],
                ),
            }
        )
    )
    scenario = scenario.model_copy(
        update={
            "behaviours": behaviours,
        }
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
    metric_generator = generators[
        metric_behaviour_index
    ]
    assert isinstance(
        metric_generator,
        MetricGenerator,
    )
    assert metric_generator._metric_ids == (
        "request_latency",
        "error_rate",
    )


def test_generator_factory_rejects_unknown_selected_metric() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )
    metric_behaviour_index = next(
        index
        for index, behaviour in enumerate(
            scenario.behaviours
        )
        if behaviour.source == SourceDomain.METRIC
    )
    behaviours = list(scenario.behaviours)
    behaviours[metric_behaviour_index] = (
        behaviours[metric_behaviour_index].model_copy(
            update={
                "selection": ScenarioMetricSelection(
                    metric_ids=[
                        "does_not_exist",
                    ],
                ),
            }
        )
    )
    scenario = scenario.model_copy(
        update={
            "behaviours": behaviours,
        }
    )
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    with pytest.raises(
        ValueError,
        match="Missing Metric Definition: does_not_exist",
    ):
        GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build(
            scenario=scenario,
            enterprise=enterprise,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
        )


def test_generator_factory_rejects_selected_metric_missing_from_service_baseline() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )
    metric_behaviour_index = next(
        index
        for index, behaviour in enumerate(
            scenario.behaviours
        )
        if behaviour.source == SourceDomain.METRIC
    )
    behaviours = list(scenario.behaviours)
    behaviours[metric_behaviour_index] = (
        behaviours[metric_behaviour_index].model_copy(
            update={
                "selection": ScenarioMetricSelection(
                    metric_ids=[
                        "throughput",
                    ],
                ),
            }
        )
    )
    scenario = scenario.model_copy(
        update={
            "behaviours": behaviours,
        }
    )
    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )
    payment_service_index = next(
        index
        for index, service in enumerate(
            enterprise.services
        )
        if service.service_id == "payment_service"
    )
    services = list(enterprise.services)
    services[payment_service_index] = (
        services[payment_service_index].model_copy(
            update={
                "baseline_profile_id": (
                    "business_workflow_nominal"
                ),
            }
        )
    )
    enterprise = enterprise.model_copy(
        update={
            "services": services,
        }
    )
    with pytest.raises(
        ValueError,
        match="Missing Metric Baseline: throughput",
    ):
        GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build(
            scenario=scenario,
            enterprise=enterprise,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
        )


def test_generator_factory_passes_capacity_profile_to_metric_generator() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )
    metric_behaviour_index = next(
        index
        for index, behaviour in enumerate(
            scenario.behaviours
        )
        if behaviour.source == SourceDomain.METRIC
    )
    behaviours = list(scenario.behaviours)
    behaviours[metric_behaviour_index] = (
        behaviours[metric_behaviour_index].model_copy(
            update={
                "profile_id": CAPACITY_PRESSURE,
                "selection": ScenarioMetricSelection(
                    metric_ids=["throughput"],
                ),
            }
        )
    )
    scenario = scenario.model_copy(
        update={
            "behaviours": behaviours,
        }
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
    metric_generator = generators[
        metric_behaviour_index
    ]
    assert isinstance(
        metric_generator,
        MetricGenerator,
    )
    assert (
        metric_generator._capacity_profile
        is not None
    )
    assert (
        metric_generator._capacity_profile.profile_id
        == "critical_payment_capacity"
    )


def test_generator_factory_builds_bank_04_capacity_scenario() -> None:
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-04.yaml"
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
    capacity_generators = [
        generator
        for generator in generators
        if (
            isinstance(generator, MetricGenerator)
            and generator._behaviour.profile_id
            in {
                "capacity_pressure",
                "capacity_saturation",
                "capacity_recovery",
            }
        )
    ]
    assert len(capacity_generators) == 3
    for generator in capacity_generators:
        assert generator._metric_ids == (
            "throughput",
        )
        assert (
            generator._capacity_profile
            is not None
        )
        assert (
            generator._capacity_profile.profile_id
            == "critical_payment_capacity"
        )


def test_generator_factory_uses_execution_target_service_for_metric_runtime() -> None:
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
    execution_target = ScenarioExecutionTarget(
        business_stream="core_banking",
        service="account_service",
        component="account_database",
        environment=Environment.PRODUCTION,
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
        ).build(
            scenario=scenario,
            enterprise=enterprise,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
            execution_target=execution_target,
        )


def test_generator_factory_rejects_unknown_execution_target_service() -> None:
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
    execution_target = ScenarioExecutionTarget(
        business_stream="core_banking",
        service="missing_service",
        component=None,
        environment=Environment.PRODUCTION,
    )
    with pytest.raises(
        ValueError,
        match=(
            "Execution target Service was not found "
            "in Enterprise: missing_service"
        ),
    ):
        GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build(
            scenario=scenario,
            enterprise=enterprise,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
            execution_target=execution_target,
        )


def test_generator_factory_keeps_itsm_on_declared_scenario_scope() -> None:
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
    itsm_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.ITSM
    )
    scenario = scenario.model_copy(
        update={
            "behaviours": [
                itsm_behaviour,
            ],
        }
    )
    execution_target = ScenarioExecutionTarget(
        business_stream="core_banking",
        service="account_service",
        component="account_database",
        environment=Environment.PRODUCTION,
    )
    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
        execution_target=execution_target,
    )
    assert len(generators) == 1
    itsm_generator = generators[0]
    assert isinstance(
        itsm_generator,
        ITSMGenerator,
    )
    assert (
        itsm_generator._service_owner
        == "payments_operations"
    )
    assert (
        itsm_generator._component_ids
        == scenario.target.component_ids
    )
