import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
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
from synthetic_ops_generator.domain.enums import OperationalState
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestGenerator,
)
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
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)

SCENARIO_PATH = Path(
    "config/scenarios/banking/BANK-07.yaml"
)

ENTERPRISE_PATH = Path(
    "config/enterprises/bank_alpha"
)


def test_bank_07_missing_approval_and_incomplete_evidence() -> None:
    scenario = load_scenario(SCENARIO_PATH)

    enterprise = load_enterprise_configuration(
        ENTERPRISE_PATH
    )

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )

    assert scenario.scenario_id == "BANK-07"
    assert scenario.target.enterprise_id == "bank_alpha"
    assert scenario.target.business_stream_id == "payments"
    assert scenario.target.service_id == "payment_service"

    assert scenario.target.component_ids == [
        "payment_api",
        "payment_database",
        "payment_worker",
    ]

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

    log_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.LOG
    )

    incident_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.INCIDENT
    )

    evidence_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.EVIDENCE
    )

    assert itsm_behaviour.profile_id == (
        "missing_required_approval"
    )
    assert itsm_behaviour.during_state == OperationalState.NORMAL

    assert (
        infrastructure_behaviour.profile_id
        == "all_required_checks_pass"
    )
    assert (
        infrastructure_behaviour.during_state
        == OperationalState.NORMAL
    )

    assert (
        deployment_behaviour.profile_id
        == "successful_deployment"
    )
    assert (
        deployment_behaviour.during_state
        == OperationalState.IMPLEMENTING
    )

    assert (
        application_behaviour.profile_id
        == "all_mandatory_tests_pass"
    )
    assert (
        application_behaviour.during_state
        == OperationalState.OBSERVING
    )

    assert (
        log_behaviour.profile_id
        == "normal_operational_logs"
    )
    assert (
        log_behaviour.during_state
        == OperationalState.OBSERVING
    )

    assert incident_behaviour.profile_id == "no_incident"
    assert (
        incident_behaviour.during_state
        == OperationalState.OBSERVING
    )

    assert evidence_behaviour.profile_id == (
        "incomplete_validation_evidence"
    )
    assert (
        evidence_behaviour.during_state
        == OperationalState.OBSERVING
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

    assert service.baseline_profile_id is not None

    baseline_profile = load_baseline_profile(
        service.baseline_profile_id
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
        LogGenerator(
            ids=ids,
            behaviour=log_behaviour,
        ),
        IncidentGenerator(
            ids=ids,
            behaviour=incident_behaviour,
        ),
        EvidenceGenerator(
            ids=ids,
            behaviour=evidence_behaviour,
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

    validation_report = CrossSourceValidator().validate(
        events=runner.event_history,
        context=context,
        enterprise=enterprise,
    )

    assert validation_report.is_valid is True
    assert validation_report.findings == []

    assert visited_states == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]

    assert len(publisher.events) == 31

    assert [
        event.sequence_number
        for event in publisher.events
    ] == list(range(1, 32))

    event_times = [
        event.event_time
        for event in publisher.events
    ]

    assert event_times == sorted(event_times)
    assert len(set(event_times)) == 31

    assert list(runner.event_history) == publisher.events

    itsm_events = [
        event
        for event in publisher.events
        if event.source_system == "synthetic_itsm"
    ]

    assert [
        event.event_type
        for event in itsm_events
    ] == [
        "itsm.change.created",
        "itsm.approval.missing",
    ]

    change = itsm_events[0].data["change"]
    approval = itsm_events[1].data["approval"]

    assert change["status"] == "created"
    assert approval["status"] == "missing"

    assert (
        itsm_events[1].data["change_status"]
        == "created"
    )

    assert not any(
        event.event_type == "itsm.approval.approved"
        for event in publisher.events
    )

    application_events = [
        event
        for event in publisher.events
        if event.event_type.startswith(
            "application_test."
        )
    ]

    assert len(application_events) == 6

    assert not any(
        event.event_type == "application_test.failed"
        for event in application_events
    )

    metric_events = [
        event
        for event in publisher.events
        if event.event_type == "metric.observed"
    ]

    assert len(metric_events) == 6

    assert {
        event.data["metric"]["classification"]
        for event in metric_events
    } == {"normal"}

    log_events = [
        event
        for event in publisher.events
        if event.event_type == "log.observed"
    ]

    assert len(log_events) == 3

    assert {
        event.data["log"]["severity"]
        for event in log_events
    } == {"info"}

    incident_events = [
        event
        for event in publisher.events
        if event.event_type.startswith("itsm.incident.")
    ]

    assert incident_events == []
    assert context.incident_id is None

    evidence_events = [
        event
        for event in publisher.events
        if event.event_type == "evidence.captured"
    ]

    assert len(evidence_events) == 5

    assert [
        event.data["evidence"]["evidence_type"]
        for event in evidence_events
    ] == [
        "infrastructure_validation",
        "deployment_result",
        "application_validation",
        "pre_change_baseline",
        "post_change_observation",
    ]

    assert not any(
        event.data["evidence"]["evidence_type"]
        == "change_approval"
        for event in evidence_events
    )

    event_by_id = {
        event.event_id: event
        for event in publisher.events
    }

    for evidence_event in evidence_events:
        evidence = evidence_event.data["evidence"]

        assert evidence["source_event_ids"]

        for source_event_id in evidence[
            "source_event_ids"
        ]:
            assert source_event_id in event_by_id

            source_event = event_by_id[
                source_event_id
            ]

            assert (
                source_event.sequence_number
                < evidence_event.sequence_number
            )

    assert (
        scenario.expected_result.scenario_id
        == "BANK-07"
    )

    assert (
        scenario.expected_result.expected_decision.value
        == "incomplete"
    )

    assert (
        scenario.expected_result.expected_action.value
        == "review"
    )

    assert (
        scenario.expected_result.expected_outcome.value
        == "successful"
    )

    assert (
        scenario.expected_result.expected_incident_attribution
        is False
    )

    assert set(
        scenario.expected_result.expected_blocking_conditions
    ) == {
        "missing_required_approval",
        "missing_required_change_approval_evidence",
    }

    assert (
        context.scenario_state
        == OperationalState.COMPLETED
    )