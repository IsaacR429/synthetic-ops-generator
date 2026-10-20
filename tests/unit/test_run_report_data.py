from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.control.configuration import (
    GenerationLifecycle,
)
from synthetic_ops_generator.control.models import (
    RunExecutionMode,
    RunRecord,
    RunStatus,
    RunTargetSnapshot,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.reporting.run_report import (
    build_run_report_data,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioFrequencyOverride,
    ScenarioIntervalFrequencyOverride,
    ScenarioLogFrequencyOverride,
)


def test_run_report_data_projects_run_scenario_and_target_context() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    target = RunTargetSnapshot(
        enterprise_id=scenario.target.enterprise_id,
        business_stream_id=(
            scenario.target.business_stream_id
        ),
        service_id=scenario.target.service_id,
        component_ids=tuple(
            scenario.target.component_ids
        ),
        environment=scenario.target.environment,
    )

    started_at = datetime(
        2026,
        10,
        15,
        8,
        0,
        tzinfo=UTC,
    )
    completed_at = datetime(
        2026,
        10,
        15,
        8,
        5,
        tzinfo=UTC,
    )
    generated_at = datetime(
        2026,
        10,
        15,
        9,
        0,
        tzinfo=UTC,
    )

    run = RunRecord(
        run_id="RUN-REPORT-001",
        scenario_id=scenario.scenario_id,
        change_id="CHG-REPORT-001",
        status=RunStatus.COMPLETED,
        started_at=started_at,
        completed_at=completed_at,
        current_state=OperationalState.COMPLETED,
        event_count=0,
        validation_passed=True,
        random_seed=42,
        event_interval_seconds=5.0,
        target=target,
        execution_mode=RunExecutionMode.STANDARD,
        generation_lifecycle=GenerationLifecycle.BOUNDED,
    )

    stream = next(
        item
        for item in enterprise.business_streams
        if item.stream_id
        == target.business_stream_id
    )
    service = next(
        item
        for item in enterprise.services
        if item.service_id == target.service_id
    )
    components = tuple(
        next(
            component
            for component in enterprise.components
            if component.component_id
            == component_id
        )
        for component_id in target.component_ids
    )

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=(),
        generated_at=generated_at,
    )

    assert report.generated_at == generated_at
    assert report.context_resolution == "current_catalogue"

    assert report.execution.run_id == run.run_id
    assert (
        report.execution.scenario_id
        == scenario.scenario_id
    )
    assert (
        report.execution.change_id
        == run.change_id
    )
    assert report.execution.status == "completed"
    assert (
        report.execution.current_state
        == "completed"
    )
    assert (
        report.execution.started_at
        == started_at
    )
    assert (
        report.execution.completed_at
        == completed_at
    )
    assert report.execution.event_count == 0
    assert report.execution.validation_passed is True
    assert report.execution.random_seed == 42
    assert (
        report.execution.event_interval_seconds
        == 5.0
    )
    assert (
        report.execution.execution_mode
        == "standard"
    )
    assert (
        report.execution.generation_lifecycle
        == "bounded"
    )

    assert (
        report.scenario.scenario_id
        == scenario.scenario_id
    )
    assert report.scenario.name == scenario.name
    assert (
        report.scenario.description
        == scenario.description
    )
    assert (
        report.scenario.family
        == scenario.family.value
    )
    assert (
        report.scenario.industry
        == scenario.industry.value
    )
    assert report.scenario.risk == scenario.risk.value

    assert report.scenario.initial_conditions == tuple(
        scenario.initial_conditions
    )
    assert report.scenario.state_sequence == tuple(
        state.value
        for state in scenario.state_sequence
    )
    assert report.scenario.assumptions == tuple(
        scenario.assumptions
    )
    assert report.scenario.tags == tuple(
        scenario.tags
    )

    assert not hasattr(
        report.scenario,
        "expected_result",
    )

    assert (
        report.target.enterprise_id
        == enterprise.enterprise_id
    )
    assert (
        report.target.enterprise_name
        == enterprise.name
    )
    assert (
        report.target.enterprise_industry
        == enterprise.industry.value
    )

    assert (
        report.target.business_stream_id
        == stream.stream_id
    )
    assert (
        report.target.business_stream_name
        == stream.name
    )

    assert (
        report.target.service_id
        == service.service_id
    )
    assert (
        report.target.service_name
        == service.name
    )
    assert (
        report.target.service_owner
        == service.owner
    )
    assert (
        report.target.service_criticality
        == service.criticality.value
    )
    assert report.target.service_workload_class == (
        service.workload_class.value
        if service.workload_class is not None
        else None
    )

    assert (
        report.target.benchmark_profile_id
        == service.benchmark_profile_id
    )
    assert (
        report.target.baseline_profile_id
        == service.baseline_profile_id
    )
    assert (
        report.target.capacity_profile_id
        == service.capacity_profile_id
    )

    assert (
        report.target.environment
        == target.environment.value
    )

    assert tuple(
        component.component_id
        for component in report.target.components
    ) == tuple(
        component.component_id
        for component in components
    )

    assert tuple(
        component.name
        for component in report.target.components
    ) == tuple(
        component.name
        for component in components
    )

    assert report.evidence_rows == ()
    assert report.metric_evaluation_explanations == ()


def test_run_report_data_requires_run_target_snapshot() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    run = RunRecord(
        run_id="RUN-REPORT-NO-TARGET",
        scenario_id=scenario.scenario_id,
        change_id=None,
        status=RunStatus.COMPLETED,
        started_at=datetime(
            2026,
            10,
            15,
            8,
            0,
            tzinfo=UTC,
        ),
        completed_at=datetime(
            2026,
            10,
            15,
            8,
            5,
            tzinfo=UTC,
        ),
        current_state=OperationalState.COMPLETED,
        event_count=0,
        validation_passed=True,
        random_seed=42,
        event_interval_seconds=5.0,
        target=None,
    )

    try:
        build_run_report_data(
            run=run,
            scenario=scenario,
            enterprise=enterprise,
            events=(),
            generated_at=datetime(
                2026,
                10,
                15,
                9,
                0,
                tzinfo=UTC,
            ),
        )
    except ValueError as exc:
        assert "target snapshot" in str(exc).lower()
    else:
        raise AssertionError(
            "Expected report construction to reject "
            "a Run without a target snapshot."
        )


def _make_report_run(
    *,
    scenario,
    event_count: int = 1,
) -> RunRecord:
    return RunRecord(
        run_id="RUN-REPORT-EVIDENCE",
        scenario_id=scenario.scenario_id,
        change_id="CHG-REPORT-EVIDENCE",
        status=RunStatus.COMPLETED,
        started_at=datetime(
            2026,
            10,
            15,
            8,
            0,
            tzinfo=UTC,
        ),
        completed_at=datetime(
            2026,
            10,
            15,
            8,
            5,
            tzinfo=UTC,
        ),
        current_state=OperationalState.COMPLETED,
        event_count=event_count,
        validation_passed=True,
        random_seed=42,
        event_interval_seconds=5.0,
        target=RunTargetSnapshot(
            enterprise_id=(
                scenario.target.enterprise_id
            ),
            business_stream_id=(
                scenario.target.business_stream_id
            ),
            service_id=scenario.target.service_id,
            component_ids=tuple(
                scenario.target.component_ids
            ),
            environment=scenario.target.environment,
        ),
    )


def _make_report_event(
    *,
    run_id: str,
    scenario_id: str,
    sequence_number: int = 1,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=f"evt-report-{sequence_number}",
        event_type="metric.observed",
        schema_version="1.0",
        event_time=datetime(
            2026,
            10,
            15,
            8,
            1,
            tzinfo=UTC,
        ),
        source_system="synthetic_report_test",
        source_domain=SourceDomain.METRIC,
        scenario_id=scenario_id,
        run_id=run_id,
        chg_id="CHG-REPORT-EVIDENCE",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id=None,
        service_instance_id=None,
        sequence_number=sequence_number,
        synthetic=True,
        data={
            "report_test": True,
        },
    )


def test_run_report_data_projects_supplied_evidence() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )
    run = _make_report_run(
        scenario=scenario,
    )
    event = _make_report_event(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
    )

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=(event,),
        generated_at=datetime(
            2026,
            10,
            15,
            9,
            0,
            tzinfo=UTC,
        ),
    )

    assert len(report.evidence_rows) == 1

    row = report.evidence_rows[0]

    assert row.event_id == event.event_id
    assert row.run_id == run.run_id
    assert row.scenario_id == run.scenario_id
    assert row.sequence_number == 1
    assert (
        row.raw_event["event_id"]
        == event.event_id
    )
    assert report.metric_evaluation_explanations == ()


def test_run_report_data_rejects_evidence_from_another_run() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )
    run = _make_report_run(
        scenario=scenario,
    )
    event = _make_report_event(
        run_id="RUN-OTHER",
        scenario_id=run.scenario_id,
    )

    with pytest.raises(
        ValueError,
        match="Run ID",
    ):
        build_run_report_data(
            run=run,
            scenario=scenario,
            enterprise=enterprise,
            events=(event,),
            generated_at=datetime(
                2026,
                10,
                15,
                9,
                0,
                tzinfo=UTC,
            ),
        )


def test_run_report_data_rejects_evidence_from_another_scenario() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )
    run = _make_report_run(
        scenario=scenario,
    )
    event = _make_report_event(
        run_id=run.run_id,
        scenario_id="BANK-OTHER",
    )

    with pytest.raises(
        ValueError,
        match="Scenario ID",
    ):
        build_run_report_data(
            run=run,
            scenario=scenario,
            enterprise=enterprise,
            events=(event,),
            generated_at=datetime(
                2026,
                10,
                15,
                9,
                0,
                tzinfo=UTC,
            ),
        )


def test_run_report_data_preserves_one_shot_event_iterable() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )
    run = _make_report_run(
        scenario=scenario,
    )
    event = _make_report_event(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
    )

    def event_stream():
        yield event

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=event_stream(),
        generated_at=datetime(
            2026,
            10,
            15,
            9,
            0,
            tzinfo=UTC,
        ),
    )

    assert len(report.evidence_rows) == 1
    assert (
        report.evidence_rows[0].event_id
        == event.event_id
    )


def test_run_report_data_exposes_metric_evaluation_explanations() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )
    run = _make_report_run(
        scenario=scenario,
    )
    event = GeneratedEvent(
        event_id="evt-report-1",
        event_type="metric.observed",
        schema_version="1.0",
        event_time=datetime(
            2026,
            10,
            15,
            8,
            1,
            tzinfo=UTC,
        ),
        source_system="synthetic_report_test",
        source_domain=SourceDomain.METRIC,
        scenario_id=run.scenario_id,
        run_id=run.run_id,
        chg_id="CHG-REPORT-EVIDENCE",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id=None,
        service_instance_id=None,
        sequence_number=1,
        synthetic=True,
        data={
            "metric": {
                "metric_definition_id": "request_latency",
                "name": "Request Latency",
                "observed_value": 820.0,
                "unit": "ms",
                "evaluation_statistic": "p95",
                "direction": "lower_is_better",
                "evaluation_status": "evaluated",
                "classification": "blocking",
            },
        },
    )

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=(event,),
        generated_at=datetime(
            2026,
            10,
            15,
            9,
            0,
            tzinfo=UTC,
        ),
    )

    assert len(report.evidence_rows) == 1
    assert len(
        report.metric_evaluation_explanations
    ) == 1

    explanation = (
        report.metric_evaluation_explanations[0]
    )

    assert explanation.event_id == event.event_id
    assert (
        explanation.metric_definition_id
        == "request_latency"
    )
    assert (
        explanation.recorded_classification
        == "blocking"
    )
    assert explanation.rule is not None
    assert explanation.rule.mode == "threshold"
    assert explanation.rule.blocking_operator == ">="
    assert explanation.rule.warning_operator == ">="

def test_run_report_data_preserves_behaviour_provenance() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    run = _make_report_run(
        scenario=scenario,
    )

    event = _make_report_event(
        run_id=run.run_id,
        scenario_id=run.scenario_id,
    ).model_copy(
        update={
            "behaviour_id": (
                "metric_normal_healthy_baseline"
            )
        }
    )

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=(event,),
        generated_at=datetime(
            2026,
            10,
            17,
            2,
            0,
            tzinfo=UTC,
        ),
    )

    assert len(report.evidence_rows) == 1

    row = report.evidence_rows[0]

    assert row.behaviour_id == (
        "metric_normal_healthy_baseline"
    )
    assert row.raw_event["behaviour_id"] == (
        "metric_normal_healthy_baseline"
    )


@pytest.mark.parametrize(
    (
        "scenario_path",
        "enterprise_path",
    ),
    [
        (
            "config/scenarios/banking/BANK-01.yaml",
            "config/enterprises/bank_alpha",
        ),
        (
            "config/scenarios/insurance/INS-03.yaml",
            "config/enterprises/insurer_alpha",
        ),
        (
            "config/scenarios/banking/BANK-06.yaml",
            "config/enterprises/bank_alpha",
        ),
    ],
)
def test_run_report_data_preserves_scenario_generation_definition(
    scenario_path: str,
    enterprise_path: str,
) -> None:
    scenario = load_scenario(
        scenario_path
    )
    enterprise = load_enterprise_configuration(
        enterprise_path
    )

    run = _make_report_run(
        scenario=scenario,
        event_count=0,
    )

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=(),
        generated_at=datetime(
            2026,
            10,
            20,
            4,
            30,
            tzinfo=UTC,
        ),
    )

    projected = report.scenario

    assert projected.change_required == (
        scenario.correlation.change_required
    )

    assert projected.trigger.source == (
        scenario.trigger.source.value
    )
    assert projected.trigger.trigger_type == (
        scenario.trigger.trigger_type
    )
    assert projected.trigger.description == (
        scenario.trigger.description
    )
    assert projected.trigger.artifact == (
        scenario.trigger.artifact
    )
    assert projected.trigger.version == (
        scenario.trigger.version
    )

    assert len(projected.behaviours) == len(
        scenario.behaviours
    )

    for source, result in zip(
        scenario.behaviours,
        projected.behaviours,
        strict=True,
    ):
        assert result.behaviour_id == (
            source.behaviour_id
        )
        assert result.source == source.source.value
        assert result.during_state == (
            source.during_state.value
        )
        assert result.profile_id == source.profile_id
        assert result.description == source.description
        assert result.continuous == source.continuous
        assert result.execution_node_id == (
            source.execution_node_id
        )

        expected_metric_ids = (
            tuple(source.selection.metric_ids or ())
            if source.selection is not None
            else ()
        )
        assert result.metric_ids == (
            expected_metric_ids
        )

        expected_check_ids = (
            tuple(
                source.check_selection.check_definition_ids
            )
            if source.check_selection is not None
            else ()
        )
        assert result.check_definition_ids == (
            expected_check_ids
        )

        transition = source.resilience_transition

        assert (
            result.resilience_transition_to_execution_node_id
        ) == (
            transition.to_execution_node_id
            if transition is not None
            else None
        )

        replication = source.resilience_replication

        assert (
            result.resilience_replication_to_execution_node_id
        ) == (
            replication.to_execution_node_id
            if replication is not None
            else None
        )

        assert (
            result.resilience_replication_status
        ) == (
            replication.replication_status.value
            if replication is not None
            else None
        )

        assert (
            result.resilience_last_successful_replication_offset_seconds
        ) == (
            replication.last_successful_replication_offset_seconds
            if replication is not None
            else None
        )

    if scenario.frequency is None:
        assert projected.frequency is None
    else:
        assert projected.frequency is not None

        frequency = projected.frequency

        assert frequency.metric_interval_seconds == (
            scenario.frequency.metrics.interval_seconds
            if scenario.frequency.metrics is not None
            else None
        )

        assert frequency.log_normal_per_second == (
            scenario.frequency.logs.normal_per_second
            if scenario.frequency.logs is not None
            else None
        )
        assert frequency.log_warning_per_second == (
            scenario.frequency.logs.warning_per_second
            if scenario.frequency.logs is not None
            else None
        )
        assert frequency.log_failure_per_second == (
            scenario.frequency.logs.failure_per_second
            if scenario.frequency.logs is not None
            else None
        )

        assert (
            frequency.infrastructure_test_interval_seconds
        ) == (
            scenario.frequency.infrastructure_tests.interval_seconds
            if (
                scenario.frequency.infrastructure_tests
                is not None
            )
            else None
        )

    # Report generation context must never expose Test Oracle truth.
    assert not hasattr(
        projected,
        "expected_result",
    )


def test_run_report_data_preserves_scenario_frequency_override() -> None:
    enterprise = load_enterprise_configuration(
        "config/enterprises/bank_alpha"
    )

    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    ).model_copy(
        update={
            "frequency": ScenarioFrequencyOverride(
                metrics=ScenarioIntervalFrequencyOverride(
                    interval_seconds=2.5,
                ),
                logs=ScenarioLogFrequencyOverride(
                    normal_per_second=3.0,
                    warning_per_second=11.0,
                    failure_per_second=29.0,
                ),
                infrastructure_tests=(
                    ScenarioIntervalFrequencyOverride(
                        interval_seconds=45.0,
                    )
                ),
            )
        }
    )

    run = _make_report_run(
        scenario=scenario,
        event_count=0,
    )

    report = build_run_report_data(
        run=run,
        scenario=scenario,
        enterprise=enterprise,
        events=(),
        generated_at=datetime(
            2026,
            10,
            20,
            4,
            45,
            tzinfo=UTC,
        ),
    )

    frequency = report.scenario.frequency

    assert frequency is not None
    assert frequency.metric_interval_seconds == 2.5
    assert frequency.log_normal_per_second == 3.0
    assert frequency.log_warning_per_second == 11.0
    assert frequency.log_failure_per_second == 29.0
    assert (
        frequency.infrastructure_test_interval_seconds
        == 45.0
    )
