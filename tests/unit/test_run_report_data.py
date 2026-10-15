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
