from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)


@dataclass(frozen=True)
class RunEvidenceRow:
    sequence_number: int
    event_time: datetime

    event_id: str
    event_type: str
    schema_version: str

    source_system: str
    source_domain: str | None

    scenario_id: str
    run_id: str
    chg_id: str | None

    business_stream: str | None
    service: str | None
    component: str | None
    environment: str | None

    site_id: str | None
    service_instance_id: str | None

    synthetic: bool

    raw_event: dict[str, Any]


    behaviour_id: str | None = None
    metric_definition_id: str | None = None
    metric_name: str | None = None
    observed_value: float | None = None
    unit: str | None = None
    evaluation_statistic: str | None = None
    metric_direction: str | None = None
    evaluation_status: str | None = None
    metric_classification: str | None = None

    baseline_profile_id: str | None = None
    baseline_center: float | None = None
    baseline_noise_stddev: float | None = None
    baseline_lower_bound: float | None = None
    baseline_upper_bound: float | None = None

    benchmark_profile_id: str | None = None
    benchmark_reference_target: float | None = None
    benchmark_warning_threshold: float | None = None
    benchmark_blocking_threshold: float | None = None

    benchmark_source_id: str | None = None
    benchmark_source_type: str | None = None
    benchmark_source_name: str | None = None
    benchmark_source_reference: str | None = None
    benchmark_source_version: str | None = None
    benchmark_source_retrieved_on: str | None = None
    benchmark_source_rationale: str | None = None
    benchmark_applied_overrides: tuple[str, ...] = ()

    behaviour_profile_id: str | None = None
    scenario_state: str | None = None

    historical_counterfactual_value: float | None = None
    historical_perturbation_strength: float | None = None
    historical_perturbation_phase: str | None = None

    capacity_profile_id: str | None = None
    capacity_classification: str | None = None
    capacity_direction: str | None = None
    capacity_pressure_threshold: float | None = None
    capacity_saturation_threshold: float | None = None


def _mapping(
    value: object,
) -> dict[str, Any] | None:
    if (
        not isinstance(value, dict)
        or isinstance(value, list)
    ):
        return None

    return value


def _string(
    value: object,
) -> str | None:
    return value if isinstance(value, str) else None


def _number(
    value: object,
) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    return None


def _string_tuple(
    value: object,
) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()

    return tuple(
        item
        for item in value
        if isinstance(item, str)
    )


def project_run_evidence_row(
    event: GeneratedEvent,
) -> RunEvidenceRow:
    metric = _mapping(event.data.get("metric"))

    baseline = (
        _mapping(metric.get("baseline"))
        if metric is not None
        else None
    )

    benchmark = (
        _mapping(metric.get("effective_benchmark"))
        if metric is not None
        else None
    )

    provenance = (
        _mapping(benchmark.get("provenance"))
        if benchmark is not None
        else None
    )

    historical = (
        _mapping(metric.get("historical"))
        if metric is not None
        else None
    )

    capacity = (
        _mapping(metric.get("capacity"))
        if metric is not None
        else None
    )

    return RunEvidenceRow(
        sequence_number=event.sequence_number,
        event_time=event.event_time,
        event_id=event.event_id,
        event_type=event.event_type,
        schema_version=event.schema_version,
        source_system=event.source_system,
        source_domain=(
            event.source_domain.value
            if event.source_domain is not None
            else None
        ),
        scenario_id=event.scenario_id,
        run_id=event.run_id,
        behaviour_id=event.behaviour_id,
        chg_id=event.chg_id,
        business_stream=event.business_stream,
        service=event.service,
        component=event.component,
        environment=(
            event.environment.value
            if event.environment is not None
            else None
        ),
        site_id=event.site_id,
        service_instance_id=(
            event.service_instance_id
        ),
        synthetic=event.synthetic,
        metric_definition_id=(
            _string(metric.get("metric_definition_id"))
            if metric is not None
            else None
        ),
        metric_name=(
            _string(metric.get("name"))
            if metric is not None
            else None
        ),
        observed_value=(
            _number(metric.get("observed_value"))
            if metric is not None
            else None
        ),
        unit=(
            _string(metric.get("unit"))
            if metric is not None
            else None
        ),
        evaluation_statistic=(
            _string(metric.get("evaluation_statistic"))
            if metric is not None
            else None
        ),
        metric_direction=(
            _string(metric.get("direction"))
            if metric is not None
            else None
        ),
        evaluation_status=(
            _string(metric.get("evaluation_status"))
            if metric is not None
            else None
        ),
        metric_classification=(
            _string(metric.get("classification"))
            if metric is not None
            else None
        ),
        baseline_profile_id=(
            _string(metric.get("baseline_profile_id"))
            if metric is not None
            else None
        ),
        baseline_center=(
            _number(baseline.get("center"))
            if baseline is not None
            else None
        ),
        baseline_noise_stddev=(
            _number(baseline.get("noise_stddev"))
            if baseline is not None
            else None
        ),
        baseline_lower_bound=(
            _number(baseline.get("lower_bound"))
            if baseline is not None
            else None
        ),
        baseline_upper_bound=(
            _number(baseline.get("upper_bound"))
            if baseline is not None
            else None
        ),
        benchmark_profile_id=(
            _string(metric.get("benchmark_profile_id"))
            if metric is not None
            else None
        ),
        benchmark_reference_target=(
            _number(benchmark.get("reference_target"))
            if benchmark is not None
            else None
        ),
        benchmark_warning_threshold=(
            _number(benchmark.get("warning_threshold"))
            if benchmark is not None
            else None
        ),
        benchmark_blocking_threshold=(
            _number(benchmark.get("blocking_threshold"))
            if benchmark is not None
            else None
        ),
        benchmark_source_id=(
            _string(provenance.get("source_id"))
            if provenance is not None
            else None
        ),
        benchmark_source_type=(
            _string(provenance.get("source_type"))
            if provenance is not None
            else None
        ),
        benchmark_source_name=(
            _string(provenance.get("source_name"))
            if provenance is not None
            else None
        ),
        benchmark_source_reference=(
            _string(provenance.get("source_reference"))
            if provenance is not None
            else None
        ),
        benchmark_source_version=(
            _string(provenance.get("version"))
            if provenance is not None
            else None
        ),
        benchmark_source_retrieved_on=(
            _string(provenance.get("retrieved_on"))
            if provenance is not None
            else None
        ),
        benchmark_source_rationale=(
            _string(provenance.get("rationale"))
            if provenance is not None
            else None
        ),
        benchmark_applied_overrides=(
            _string_tuple(
                benchmark.get("applied_overrides")
            )
            if benchmark is not None
            else ()
        ),
        behaviour_profile_id=(
            _string(metric.get("behaviour_profile_id"))
            if metric is not None
            else None
        ),
        scenario_state=(
            _string(metric.get("scenario_state"))
            if metric is not None
            else None
        ),
        historical_counterfactual_value=(
            _number(
                historical.get("counterfactual_value")
            )
            if historical is not None
            else None
        ),
        historical_perturbation_strength=(
            _number(
                historical.get("perturbation_strength")
            )
            if historical is not None
            else None
        ),
        historical_perturbation_phase=(
            _string(
                historical.get("perturbation_phase")
            )
            if historical is not None
            else None
        ),
        capacity_profile_id=(
            _string(capacity.get("capacity_profile_id"))
            if capacity is not None
            else None
        ),
        capacity_classification=(
            _string(capacity.get("classification"))
            if capacity is not None
            else None
        ),
        capacity_direction=(
            _string(capacity.get("direction"))
            if capacity is not None
            else None
        ),
        capacity_pressure_threshold=(
            _number(capacity.get("pressure_threshold"))
            if capacity is not None
            else None
        ),
        capacity_saturation_threshold=(
            _number(
                capacity.get("saturation_threshold")
            )
            if capacity is not None
            else None
        ),
        raw_event=event.model_dump(mode="json"),
    )
