from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.control.models import (
    RunRecord,
    RunStatus,
)
from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.reporting.evaluation_explanation import (
    ReportMetricEvaluationExplanation,
    build_metric_evaluation_explanations,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
    project_run_evidence_row,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioDefinition,
)

DEFAULT_RUN_REPORT_EVENT_LIMIT = 250

TERMINAL_RUN_STATUSES = frozenset(
    {
        RunStatus.COMPLETED,
        RunStatus.FAILED,
        RunStatus.STOPPED,
    }
)


@dataclass(frozen=True)
class RunReportExecution:
    run_id: str
    scenario_id: str
    change_id: str | None

    status: str
    current_state: str

    started_at: datetime
    completed_at: datetime | None

    event_count: int
    validation_passed: bool | None

    random_seed: int
    event_interval_seconds: float

    execution_mode: str
    generation_lifecycle: str


@dataclass(frozen=True)
class RunReportTrigger:
    source: str
    trigger_type: str
    description: str

    artifact: str | None
    version: str | None


@dataclass(frozen=True)
class RunReportBehaviour:
    behaviour_id: str

    source: str
    during_state: str
    profile_id: str

    description: str | None
    continuous: bool

    metric_ids: tuple[str, ...]
    check_definition_ids: tuple[str, ...]

    execution_node_id: str | None

    resilience_transition_to_execution_node_id: (
        str | None
    )

    resilience_replication_to_execution_node_id: (
        str | None
    )
    resilience_replication_status: str | None
    resilience_last_successful_replication_offset_seconds: (
        float | None
    )


@dataclass(frozen=True)
class RunReportFrequency:
    metric_interval_seconds: float | None

    log_normal_per_second: float | None
    log_warning_per_second: float | None
    log_failure_per_second: float | None

    infrastructure_test_interval_seconds: float | None


@dataclass(frozen=True)
class RunReportScenario:
    scenario_id: str
    name: str
    description: str

    family: str
    industry: str
    risk: str

    change_required: bool

    trigger: RunReportTrigger
    behaviours: tuple[RunReportBehaviour, ...]
    frequency: RunReportFrequency | None

    initial_conditions: tuple[str, ...]
    state_sequence: tuple[str, ...]

    assumptions: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class RunReportComponent:
    component_id: str
    name: str
    component_type: str

    service_id: str
    environment: str


@dataclass(frozen=True)
class RunReportTarget:
    enterprise_id: str
    enterprise_name: str
    enterprise_industry: str

    business_stream_id: str
    business_stream_name: str

    service_id: str
    service_name: str
    service_owner: str
    service_criticality: str
    service_workload_class: str | None

    benchmark_profile_id: str | None
    baseline_profile_id: str | None
    capacity_profile_id: str | None

    component_ids: tuple[str, ...]
    components: tuple[RunReportComponent, ...]

    environment: str


@dataclass(frozen=True)
class RunReportScope:
    """
    Evidence-window metadata for one generated report.

    selection describes whether the report contains the complete
    retained Run event set or only the latest bounded window.
    """

    selection: str
    maximum_event_count: int

    total_retained_event_count: int
    included_event_count: int

    first_sequence_number: int | None
    last_sequence_number: int | None

    complete_run_represented: bool


@dataclass(frozen=True)
class RunReportData:
    generated_at: datetime
    context_resolution: str

    execution: RunReportExecution
    scenario: RunReportScenario
    target: RunReportTarget
    scope: RunReportScope

    evidence_rows: tuple[RunEvidenceRow, ...]
    metric_evaluation_explanations: tuple[
        ReportMetricEvaluationExplanation,
        ...,
    ]


def _project_report_behaviour(
    behaviour: ScenarioBehaviour,
) -> RunReportBehaviour:
    metric_ids = (
        tuple(behaviour.selection.metric_ids or ())
        if behaviour.selection is not None
        else ()
    )

    check_definition_ids = (
        tuple(
            behaviour.check_selection.check_definition_ids
        )
        if behaviour.check_selection is not None
        else ()
    )

    transition = behaviour.resilience_transition
    replication = behaviour.resilience_replication

    return RunReportBehaviour(
        behaviour_id=behaviour.behaviour_id,
        source=behaviour.source.value,
        during_state=behaviour.during_state.value,
        profile_id=behaviour.profile_id,
        description=behaviour.description,
        continuous=behaviour.continuous,
        metric_ids=metric_ids,
        check_definition_ids=check_definition_ids,
        execution_node_id=behaviour.execution_node_id,
        resilience_transition_to_execution_node_id=(
            transition.to_execution_node_id
            if transition is not None
            else None
        ),
        resilience_replication_to_execution_node_id=(
            replication.to_execution_node_id
            if replication is not None
            else None
        ),
        resilience_replication_status=(
            replication.replication_status.value
            if replication is not None
            else None
        ),
        resilience_last_successful_replication_offset_seconds=(
            replication.last_successful_replication_offset_seconds
            if replication is not None
            else None
        ),
    )


def _project_report_frequency(
    scenario: ScenarioDefinition,
) -> RunReportFrequency | None:
    frequency = scenario.frequency

    if frequency is None:
        return None

    metrics = frequency.metrics
    logs = frequency.logs
    infrastructure_tests = frequency.infrastructure_tests

    return RunReportFrequency(
        metric_interval_seconds=(
            metrics.interval_seconds
            if metrics is not None
            else None
        ),
        log_normal_per_second=(
            logs.normal_per_second
            if logs is not None
            else None
        ),
        log_warning_per_second=(
            logs.warning_per_second
            if logs is not None
            else None
        ),
        log_failure_per_second=(
            logs.failure_per_second
            if logs is not None
            else None
        ),
        infrastructure_test_interval_seconds=(
            infrastructure_tests.interval_seconds
            if infrastructure_tests is not None
            else None
        ),
    )


def _resolve_business_stream(
    *,
    enterprise: Enterprise,
    stream_id: str,
):
    stream = next(
        (
            candidate
            for candidate in enterprise.business_streams
            if candidate.stream_id == stream_id
        ),
        None,
    )

    if stream is None:
        raise ValueError(
            "Run target business stream "
            f"'{stream_id}' was not found in Enterprise "
            f"'{enterprise.enterprise_id}'."
        )

    return stream


def _resolve_service(
    *,
    enterprise: Enterprise,
    service_id: str,
):
    service = next(
        (
            candidate
            for candidate in enterprise.services
            if candidate.service_id == service_id
        ),
        None,
    )

    if service is None:
        raise ValueError(
            "Run target service "
            f"'{service_id}' was not found in Enterprise "
            f"'{enterprise.enterprise_id}'."
        )

    return service


def _resolve_components(
    *,
    enterprise: Enterprise,
    component_ids: tuple[str, ...],
) -> tuple[RunReportComponent, ...]:
    components: list[RunReportComponent] = []

    for component_id in component_ids:
        component = next(
            (
                candidate
                for candidate in enterprise.components
                if candidate.component_id == component_id
            ),
            None,
        )

        if component is None:
            raise ValueError(
                "Run target component "
                f"'{component_id}' was not found in Enterprise "
                f"'{enterprise.enterprise_id}'."
            )

        components.append(
            RunReportComponent(
                component_id=component.component_id,
                name=component.name,
                component_type=component.component_type,
                service_id=component.service_id,
                environment=component.environment.value,
            )
        )

    return tuple(components)


def build_run_report_data(
    *,
    run: RunRecord,
    scenario: ScenarioDefinition,
    enterprise: Enterprise,
    events: Iterable[GeneratedEvent],
    generated_at: datetime,
    total_retained_event_count: int | None = None,
    maximum_event_count: int = DEFAULT_RUN_REPORT_EVENT_LIMIT,
) -> RunReportData:
    target = run.target

    if target is None:
        raise ValueError(
            "Run report requires a Run target snapshot."
        )

    if run.scenario_id != scenario.scenario_id:
        raise ValueError(
            "Run Scenario ID does not match supplied "
            "Scenario definition."
        )

    if target.enterprise_id != enterprise.enterprise_id:
        raise ValueError(
            "Run target Enterprise ID does not match "
            "supplied Enterprise definition."
        )

    stream = _resolve_business_stream(
        enterprise=enterprise,
        stream_id=target.business_stream_id,
    )

    service = _resolve_service(
        enterprise=enterprise,
        service_id=target.service_id,
    )

    components = _resolve_components(
        enterprise=enterprise,
        component_ids=target.component_ids,
    )

    report_events = tuple(events)

    if maximum_event_count <= 0:
        raise ValueError(
            "Run report maximum event count "
            "must be greater than zero."
        )

    if len(report_events) > maximum_event_count:
        raise ValueError(
            "Run report evidence exceeds the "
            f"{maximum_event_count}-event limit."
        )

    resolved_retained_event_count = (
        len(report_events)
        if total_retained_event_count is None
        else total_retained_event_count
    )

    if resolved_retained_event_count < 0:
        raise ValueError(
            "Run report retained event count "
            "cannot be negative."
        )

    if resolved_retained_event_count < len(report_events):
        raise ValueError(
            "Run report retained event count cannot be "
            "smaller than the included evidence count."
        )

    for event in report_events:
        if event.run_id != run.run_id:
            raise ValueError(
                "Run evidence Run ID does not match "
                "Report Run ID."
            )

        if event.scenario_id != run.scenario_id:
            raise ValueError(
                "Run evidence Scenario ID does not match "
                "Report Scenario ID."
            )

    evidence_rows = tuple(
        project_run_evidence_row(event)
        for event in report_events
    )

    included_event_count = len(
        evidence_rows
    )

    complete_retained_selection = (
        included_event_count
        == resolved_retained_event_count
    )

    report_scope = RunReportScope(
        selection=(
            "complete"
            if complete_retained_selection
            else "latest"
        ),
        maximum_event_count=maximum_event_count,
        total_retained_event_count=(
            resolved_retained_event_count
        ),
        included_event_count=included_event_count,
        first_sequence_number=(
            evidence_rows[0].sequence_number
            if evidence_rows
            else None
        ),
        last_sequence_number=(
            evidence_rows[-1].sequence_number
            if evidence_rows
            else None
        ),
        complete_run_represented=(
            run.status in TERMINAL_RUN_STATUSES
            and complete_retained_selection
            and resolved_retained_event_count
            == run.event_count
        ),
    )

    return RunReportData(
        generated_at=generated_at,
        context_resolution="current_catalogue",
        execution=RunReportExecution(
            run_id=run.run_id,
            scenario_id=run.scenario_id,
            change_id=run.change_id,
            status=run.status.value,
            current_state=run.current_state.value,
            started_at=run.started_at,
            completed_at=run.completed_at,
            event_count=run.event_count,
            validation_passed=run.validation_passed,
            random_seed=run.random_seed,
            event_interval_seconds=(
                run.event_interval_seconds
            ),
            execution_mode=run.execution_mode.value,
            generation_lifecycle=(
                run.generation_lifecycle.value
            ),
        ),
        scenario=RunReportScenario(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            description=scenario.description,
            family=scenario.family.value,
            industry=scenario.industry.value,
            risk=scenario.risk.value,
            change_required=(
                scenario.correlation.change_required
            ),
            trigger=RunReportTrigger(
                source=scenario.trigger.source.value,
                trigger_type=scenario.trigger.trigger_type,
                description=scenario.trigger.description,
                artifact=scenario.trigger.artifact,
                version=scenario.trigger.version,
            ),
            behaviours=tuple(
                _project_report_behaviour(behaviour)
                for behaviour in scenario.behaviours
            ),
            frequency=_project_report_frequency(
                scenario
            ),
            initial_conditions=tuple(
                scenario.initial_conditions
            ),
            state_sequence=tuple(
                state.value
                for state in scenario.state_sequence
            ),
            assumptions=tuple(
                scenario.assumptions
            ),
            tags=tuple(
                scenario.tags
            ),
        ),
        target=RunReportTarget(
            enterprise_id=enterprise.enterprise_id,
            enterprise_name=enterprise.name,
            enterprise_industry=(
                enterprise.industry.value
            ),
            business_stream_id=stream.stream_id,
            business_stream_name=stream.name,
            service_id=service.service_id,
            service_name=service.name,
            service_owner=service.owner,
            service_criticality=(
                service.criticality.value
            ),
            service_workload_class=(
                service.workload_class.value
                if service.workload_class is not None
                else None
            ),
            benchmark_profile_id=(
                service.benchmark_profile_id
            ),
            baseline_profile_id=(
                service.baseline_profile_id
            ),
            capacity_profile_id=(
                service.capacity_profile_id
            ),
            component_ids=target.component_ids,
            components=components,
            environment=target.environment.value,
        ),
        scope=report_scope,
        evidence_rows=evidence_rows,
        metric_evaluation_explanations=(
            build_metric_evaluation_explanations(
                evidence_rows
            )
        ),
    )
