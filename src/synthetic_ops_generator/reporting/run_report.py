from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from synthetic_ops_generator.control.models import (
    RunRecord,
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
    ScenarioDefinition,
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
class RunReportScenario:
    scenario_id: str
    name: str
    description: str

    family: str
    industry: str
    risk: str

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
class RunReportData:
    generated_at: datetime
    context_resolution: str

    execution: RunReportExecution
    scenario: RunReportScenario
    target: RunReportTarget

    evidence_rows: tuple[RunEvidenceRow, ...]
    metric_evaluation_explanations: tuple[
        ReportMetricEvaluationExplanation,
        ...,
    ]


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
        evidence_rows=evidence_rows,
        metric_evaluation_explanations=(
            build_metric_evaluation_explanations(
                evidence_rows
            )
        ),
    )
