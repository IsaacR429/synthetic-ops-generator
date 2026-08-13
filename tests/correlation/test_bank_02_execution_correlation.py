import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.baselines.models import BaselineProfile
from synthetic_ops_generator.benchmarks.models import BenchmarkCatalogue
from synthetic_ops_generator.benchmarks.resolver import resolve_benchmark
from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.config.loader import load_yaml_model
from synthetic_ops_generator.core.clock import ManualSimulationClock
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import OperationalState
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestGenerator,
)
from synthetic_ops_generator.generators.deployment import (
    DeploymentGenerator,
)
from synthetic_ops_generator.generators.evidence import EvidenceGenerator
from synthetic_ops_generator.generators.incident import IncidentGenerator
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.generators.itsm import ITSMGenerator
from synthetic_ops_generator.generators.log import LogGenerator
from synthetic_ops_generator.generators.metric import MetricGenerator
from synthetic_ops_generator.metrics.models import MetricCatalogue
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.runner import ScenarioRunner
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)

SCENARIO_PATH = Path(
    "config/scenarios/banking/BANK-02.yaml"
)

ENTERPRISE_PATH = Path(
    "config/enterprises/bank_alpha"
)


def test_bank_02_regression_rollback_recovery() -> None:
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

    def behaviour(
        source: SourceDomain,
        state: OperationalState,
    ) -> ScenarioBehaviour:
        return next(
            item
            for item in scenario.behaviours
            if (
                item.source == source
                and item.during_state == state
            )
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
            13,
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
            behaviour=behaviour(
                SourceDomain.ITSM,
                OperationalState.NORMAL,
            ),
            service_owner=service.owner,
            component_ids=scenario.target.component_ids,
        ),
        MetricGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.METRIC,
                OperationalState.NORMAL,
            ),
            definitions=metric_catalogue.definitions,
            baseline_profile=baseline_profile,
            benchmarks=resolved_benchmarks,
            benchmark_profile_id=benchmark_profile.profile_id,
            random_source=random_source,
        ),
        InfrastructureTestGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.INFRASTRUCTURE_TEST,
                OperationalState.NORMAL,
            ),
        ),
        DeploymentGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.DEPLOYMENT,
                OperationalState.IMPLEMENTING,
            ),
            artifact=scenario.trigger.artifact,
            artifact_version=scenario.trigger.version,
        ),
        ApplicationTestGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.APPLICATION_TEST,
                OperationalState.OBSERVING,
            ),
        ),
        MetricGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.METRIC,
                OperationalState.DEGRADED,
            ),
            definitions=metric_catalogue.definitions,
            baseline_profile=baseline_profile,
            benchmarks=resolved_benchmarks,
            benchmark_profile_id=benchmark_profile.profile_id,
            random_source=random_source,
        ),
        LogGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.LOG,
                OperationalState.DEGRADED,
            ),
        ),
        IncidentGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.INCIDENT,
                OperationalState.DEGRADED,
            ),
            event_history=runner.event_history,
        ),
        DeploymentGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.DEPLOYMENT,
                OperationalState.ROLLBACK,
            ),
            artifact=scenario.trigger.artifact,
            artifact_version=scenario.trigger.version,
        ),
        MetricGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.METRIC,
                OperationalState.RECOVERY,
            ),
            definitions=metric_catalogue.definitions,
            baseline_profile=baseline_profile,
            benchmarks=resolved_benchmarks,
            benchmark_profile_id=benchmark_profile.profile_id,
            random_source=random_source,
        ),
        LogGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.LOG,
                OperationalState.RECOVERY,
            ),
        ),
        IncidentGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.INCIDENT,
                OperationalState.RECOVERY,
            ),
            event_history=runner.event_history,
        ),
        EvidenceGenerator(
            ids=ids,
            behaviour=behaviour(
                SourceDomain.EVIDENCE,
                OperationalState.RECOVERY,
            ),
            event_history=runner.event_history,
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

    report = CrossSourceValidator().validate(
        events=runner.event_history,
        context=context,
        enterprise=enterprise,
    )

    assert report.is_valid is True
    assert report.findings == []

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "degraded",
        "rollback",
        "recovery",
        "completed",
    ]

    assert len(publisher.events) == 45

    assert [
        event.sequence_number
        for event in publisher.events
    ] == list(range(1, 46))

    event_times = [
        event.event_time
        for event in publisher.events
    ]

    assert event_times == sorted(event_times)
    assert len(set(event_times)) == 45

    assert list(runner.event_history) == publisher.events

    application_events = [
        event
        for event in publisher.events
        if event.event_type.startswith(
            "application_test."
        )
    ]

    failed_tests = [
        event
        for event in application_events
        if event.event_type == "application_test.failed"
    ]

    assert len(application_events) == 6
    assert len(failed_tests) == 1

    failed_test = failed_tests[0].data["test"]

    assert failed_test["mandatory"] is True
    assert failed_test["result"] == "failed"
    assert failed_test["failure_reason"]

    metric_events = [
        event
        for event in publisher.events
        if event.event_type == "metric.observed"
    ]

    assert len(metric_events) == 9

    degraded_metrics = [
        event
        for event in metric_events
        if (
            event.data["metric"]["scenario_state"]
            == "degraded"
        )
    ]

    recovery_metrics = [
        event
        for event in metric_events
        if (
            event.data["metric"]["scenario_state"]
            == "recovery"
        )
    ]

    assert len(degraded_metrics) == 3
    assert len(recovery_metrics) == 3

    assert {
        event.data["metric"]["classification"]
        for event in degraded_metrics
    } == {"blocking"}

    assert {
        event.data["metric"]["classification"]
        for event in recovery_metrics
    } == {"normal"}

    log_events = [
        event
        for event in publisher.events
        if event.event_type == "log.observed"
    ]

    assert len(log_events) == 6

    degraded_logs = [
        event
        for event in log_events
        if event.data["scenario_state"] == "degraded"
    ]

    recovery_logs = [
        event
        for event in log_events
        if event.data["scenario_state"] == "recovery"
    ]

    assert len(degraded_logs) == 3
    assert len(recovery_logs) == 3

    assert {
        event.data["log"]["severity"]
        for event in degraded_logs
    } == {
        "error",
        "warning",
    }

    assert {
        event.data["log"]["severity"]
        for event in recovery_logs
    } == {"info"}

    deployment_events = [
        event
        for event in publisher.events
        if event.event_type.startswith(
            "cicd.deployment."
        )
    ]

    assert [
        event.event_type
        for event in deployment_events
    ] == [
        "cicd.deployment.created",
        "cicd.deployment.started",
        "cicd.deployment.completed",
        "cicd.deployment.rollback_started",
        "cicd.deployment.rollback_completed",
    ]

    assert {
        event.data["deployment"]["deployment_id"]
        for event in deployment_events
    } == {"DEP0000001"}

    assert context.deployment_id == "DEP0000001"

    incident_events = [
        event
        for event in publisher.events
        if event.event_type.startswith(
            "itsm.incident."
        )
    ]

    assert [
        event.event_type
        for event in incident_events
    ] == [
        "itsm.incident.created",
        "itsm.incident.resolved",
    ]

    created_incident = incident_events[0].data["incident"]
    resolved_incident = incident_events[1].data["incident"]

    assert (
        created_incident["incident_id"]
        == resolved_incident["incident_id"]
        == "INC0000001"
    )

    assert created_incident["status"] == "open"
    assert resolved_incident["status"] == "resolved"

    assert (
        created_incident["chg_id"]
        == resolved_incident["chg_id"]
        == context.chg_id
    )

    assert (
        created_incident["service"]
        == resolved_incident["service"]
        == "payment_service"
    )

    assert (
        created_incident["component"]
        == resolved_incident["component"]
    )

    assert context.incident_id == "INC0000001"

    evidence_events = [
        event
        for event in publisher.events
        if event.event_type == "evidence.captured"
    ]

    assert len(evidence_events) == 9

    assert [
        event.data["evidence"]["evidence_type"]
        for event in evidence_events
    ] == [
        "change_approval",
        "infrastructure_validation",
        "deployment_result",
        "application_regression",
        "degraded_observation",
        "incident_record",
        "rollback_result",
        "recovery_observation",
        "incident_resolution",
    ]

    event_by_id = {
        event.event_id: event
        for event in publisher.events
    }

    for evidence_event in evidence_events:
        source_event_ids = (
            evidence_event.data["evidence"][
                "source_event_ids"
            ]
        )

        assert source_event_ids

        for source_event_id in source_event_ids:
            assert source_event_id in event_by_id

            assert (
                event_by_id[
                    source_event_id
                ].sequence_number
                < evidence_event.sequence_number
            )

    assert scenario.expected_result.scenario_id == "BANK-02"

    assert (
        scenario.expected_result.expected_decision
        is not None
    )
    assert (
        scenario.expected_result.expected_decision.value
        == "fail"
    )

    assert (
        scenario.expected_result.expected_action
        is not None
    )
    assert (
        scenario.expected_result.expected_action.value
        == "rollback"
    )

    assert (
        scenario.expected_result.expected_outcome.value
        == "rolled_back"
    )

    assert (
        scenario.expected_result.expected_incident_attribution
        is True
    )

    assert context.scenario_state == OperationalState.COMPLETED