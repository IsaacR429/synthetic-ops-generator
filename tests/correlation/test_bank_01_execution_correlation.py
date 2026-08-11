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
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.generators.metric import (
    MetricGenerator,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
)
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import SourceDomain
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)

SCENARIO_PATH = Path(
    "config/scenarios/banking/BANK-01.yaml"
)

ENTERPRISE_PATH = Path(
    "config/enterprises/bank_alpha"
)


def test_bank_01_itsm_and_deployment_execution() -> None:
    scenario = load_scenario(SCENARIO_PATH)

    enterprise = load_enterprise_configuration(
        ENTERPRISE_PATH
    )

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )

    service = next(
        service
        for service in enterprise.services
        if service.service_id == scenario.target.service_id
    )

    itsm_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.ITSM
    )

    metric_behaviours = [
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    ]

    assert len(metric_behaviours) == 2

    baseline_metric_behaviour = next(
        behaviour
        for behaviour in metric_behaviours
        if behaviour.profile_id == "healthy_baseline"
    )

    post_change_metric_behaviour = next(
        behaviour
        for behaviour in metric_behaviours
        if behaviour.profile_id == "healthy_post_change"
    )

    infrastructure_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.source
            == SourceDomain.INFRASTRUCTURE_TEST
        )
    )

    deployment_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.DEPLOYMENT
    )

    application_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.source
            == SourceDomain.APPLICATION_TEST
        )
    )

    assert scenario.trigger.artifact is not None
    assert scenario.trigger.version is not None

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

    assert service.benchmark_profile_id is not None
    benchmark_profile = benchmark_catalogue.profiles[
        service.benchmark_profile_id
    ]

    resolved_benchmarks = {
        metric_id: resolve_benchmark(
            metric_catalogue.definitions[metric_id],
            benchmark_profile.metrics[metric_id],
        )
        for metric_id in baseline_profile.metrics
    }

    ids = IdFactory()

    clock = ManualSimulationClock(
        datetime(
            2026,
            8,
            11,
            10,
            0,
            tzinfo=UTC,
        )
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

    generators = [
        ITSMGenerator(
            ids=ids,
            behaviour=itsm_behaviour,
            service_owner=service.owner,
            component_ids=scenario.target.component_ids,
        ),
        MetricGenerator(
            ids=ids,
            behaviour=baseline_metric_behaviour,
            definitions=metric_catalogue.definitions,
            baseline_profile=baseline_profile,
            benchmarks=resolved_benchmarks,
            benchmark_profile_id=(
                benchmark_profile.profile_id
            ),
            random_source=random_source,
        ),
        InfrastructureTestGenerator(
            ids=ids,
            behaviour=infrastructure_behaviour,
        ),
        DeploymentGenerator(
            ids=ids,
            behaviour=deployment_behaviour,
            artifact=scenario.trigger.artifact,
            artifact_version=scenario.trigger.version,
        ),
        ApplicationTestGenerator(
            ids=ids,
            behaviour=application_behaviour,
        ),
        MetricGenerator(
            ids=ids,
            behaviour=post_change_metric_behaviour,
            definitions=metric_catalogue.definitions,
            baseline_profile=baseline_profile,
            benchmarks=resolved_benchmarks,
            benchmark_profile_id=(
                benchmark_profile.profile_id
            ),
            random_source=random_source,
        ),
    ]

    visited_states = asyncio.run(
        runner.execute(
            scenario=scenario,
            context=context,
            generators=generators,
            publisher=publisher,
            event_interval_seconds=5,
        )
    )

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert len(publisher.events) == 23

    assert [
        event.event_type
        for event in publisher.events
    ] == [
        "itsm.change.created",
        "itsm.approval.approved",
        "metric.observed",
        "metric.observed",
        "metric.observed",
        "infrastructure_test.planned",
        "infrastructure_test.passed",
        "infrastructure_test.planned",
        "infrastructure_test.passed",
        "infrastructure_test.planned",
        "infrastructure_test.passed",
        "cicd.deployment.created",
        "cicd.deployment.started",
        "cicd.deployment.completed",
        "application_test.planned",
        "application_test.passed",
        "application_test.planned",
        "application_test.passed",
        "application_test.planned",
        "application_test.passed",
        "metric.observed",
        "metric.observed",
        "metric.observed",
    ]

    assert {
        event.scenario_id
        for event in publisher.events
    } == {"BANK-01"}

    assert {
        event.run_id
        for event in publisher.events
    } == {context.run_id}

    assert {
        event.chg_id
        for event in publisher.events
    } == {context.chg_id}

    assert {
        event.business_stream
        for event in publisher.events
    } == {"payments"}

    assert {
        event.service
        for event in publisher.events
    } == {"payment_service"}

    assert [
        event.sequence_number
        for event in publisher.events
    ] == list(range(1, 24))

    event_times = [
        event.event_time
        for event in publisher.events
    ]

    assert event_times == sorted(event_times)

    assert len(set(event_times)) == 23

    source_systems = {
        event.source_system
        for event in publisher.events
    }

    assert source_systems == {
        "synthetic_itsm",
        "synthetic_observability",
        "synthetic_infrastructure_test",
        "synthetic_deployment",
        "synthetic_application_test",
    }

    test_events = [
        event
        for event in publisher.events
        if event.event_type.startswith(
            (
                "infrastructure_test.",
                "application_test.",
            )
        )
    ]

    test_ids = [
        event.data["test"]["test_id"]
        for event in test_events
    ]

    assert set(test_ids) == {
        "TST0000001",
        "TST0000002",
        "TST0000003",
        "TST0000004",
        "TST0000005",
        "TST0000006",
    }

    metric_events = [
        event
        for event in publisher.events
        if event.event_type == "metric.observed"
    ]

    assert len(metric_events) == 6

    metric_ids = [
        event.data["metric"]["metric_definition_id"]
        for event in metric_events
    ]

    assert metric_ids.count("request_latency") == 2
    assert metric_ids.count("error_rate") == 2
    assert metric_ids.count("availability") == 2

    assert {
        event.data["metric"]["classification"]
        for event in metric_events
    } == {"normal"}

    assert {
        event.data["metric"]["behaviour_profile_id"]
        for event in metric_events
    } == {
        "healthy_baseline",
        "healthy_post_change",
    }

    assert {
        event.data["metric"]["scenario_state"]
        for event in metric_events
    } == {
        "normal",
        "observing",
    }

    for metric_id in (
        "request_latency",
        "error_rate",
        "availability",
    ):
        observations = [
            event.data["metric"]
            for event in metric_events
            if (
                event.data["metric"][
                    "metric_definition_id"
                ]
                == metric_id
            )
        ]

        assert len(observations) == 2

        assert (
            observations[0]["effective_benchmark"]
            == observations[1]["effective_benchmark"]
        )

        assert (
            observations[0]["baseline_profile_id"]
            == observations[1]["baseline_profile_id"]
            == "critical_interactive_nominal"
        )

        assert (
            observations[0]["benchmark_profile_id"]
            == observations[1]["benchmark_profile_id"]
            == "critical_interactive_transaction"
        )

    assert context.deployment_id == "DEP0000001"
    assert context.scenario_state.value == "completed"