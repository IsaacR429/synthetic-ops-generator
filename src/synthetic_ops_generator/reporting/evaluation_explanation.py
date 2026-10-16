from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from synthetic_ops_generator.metrics.models import (
    MetricClassification,
    MetricDirection,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
)


@dataclass(frozen=True)
class ReportMetricBaseline:
    profile_id: str | None

    center: float | None
    noise_stddev: float | None
    lower_bound: float | None
    upper_bound: float | None


@dataclass(frozen=True)
class ReportBenchmarkProvenance:
    source_id: str | None
    source_type: str | None
    source_name: str | None
    source_reference: str | None

    version: str | None
    retrieved_on: str | None
    rationale: str | None


@dataclass(frozen=True)
class ReportMetricBenchmark:
    profile_id: str | None

    reference_target: float | None
    warning_threshold: float | None
    blocking_threshold: float | None

    provenance: ReportBenchmarkProvenance | None

    applied_overrides: tuple[str, ...]


@dataclass(frozen=True)
class ReportMetricEvaluationRule:
    mode: str

    evaluation_order: tuple[str, ...]

    blocking_operator: str | None
    warning_operator: str | None

    fallback_classification: str | None


@dataclass(frozen=True)
class ReportMetricEvaluationExplanation:
    event_id: str
    sequence_number: int

    metric_definition_id: str
    metric_name: str | None

    observed_value: float | None
    unit: str | None
    evaluation_statistic: str | None

    direction: str | None
    evaluation_status: str | None

    recorded_classification: str | None

    rule: ReportMetricEvaluationRule | None

    baseline: ReportMetricBaseline | None
    benchmark: ReportMetricBenchmark | None

    behaviour_profile_id: str | None
    scenario_state: str | None


def _has_baseline_context(
    row: RunEvidenceRow,
) -> bool:
    return any(
        value is not None
        for value in (
            row.baseline_profile_id,
            row.baseline_center,
            row.baseline_noise_stddev,
            row.baseline_lower_bound,
            row.baseline_upper_bound,
        )
    )


def _build_baseline(
    row: RunEvidenceRow,
) -> ReportMetricBaseline | None:
    if not _has_baseline_context(row):
        return None

    return ReportMetricBaseline(
        profile_id=row.baseline_profile_id,
        center=row.baseline_center,
        noise_stddev=row.baseline_noise_stddev,
        lower_bound=row.baseline_lower_bound,
        upper_bound=row.baseline_upper_bound,
    )


def _has_provenance_context(
    row: RunEvidenceRow,
) -> bool:
    return any(
        value is not None
        for value in (
            row.benchmark_source_id,
            row.benchmark_source_type,
            row.benchmark_source_name,
            row.benchmark_source_reference,
            row.benchmark_source_version,
            row.benchmark_source_retrieved_on,
            row.benchmark_source_rationale,
        )
    )


def _build_provenance(
    row: RunEvidenceRow,
) -> ReportBenchmarkProvenance | None:
    if not _has_provenance_context(row):
        return None

    return ReportBenchmarkProvenance(
        source_id=row.benchmark_source_id,
        source_type=row.benchmark_source_type,
        source_name=row.benchmark_source_name,
        source_reference=(
            row.benchmark_source_reference
        ),
        version=row.benchmark_source_version,
        retrieved_on=(
            row.benchmark_source_retrieved_on
        ),
        rationale=row.benchmark_source_rationale,
    )


def _has_benchmark_context(
    row: RunEvidenceRow,
) -> bool:
    return (
        any(
            value is not None
            for value in (
                row.benchmark_profile_id,
                row.benchmark_reference_target,
                row.benchmark_warning_threshold,
                row.benchmark_blocking_threshold,
                row.benchmark_source_id,
                row.benchmark_source_type,
                row.benchmark_source_name,
                row.benchmark_source_reference,
                row.benchmark_source_version,
                row.benchmark_source_retrieved_on,
                row.benchmark_source_rationale,
            )
        )
        or bool(row.benchmark_applied_overrides)
    )


def _build_benchmark(
    row: RunEvidenceRow,
) -> ReportMetricBenchmark | None:
    if not _has_benchmark_context(row):
        return None

    return ReportMetricBenchmark(
        profile_id=row.benchmark_profile_id,
        reference_target=(
            row.benchmark_reference_target
        ),
        warning_threshold=(
            row.benchmark_warning_threshold
        ),
        blocking_threshold=(
            row.benchmark_blocking_threshold
        ),
        provenance=_build_provenance(row),
        applied_overrides=(
            row.benchmark_applied_overrides
        ),
    )


def _build_evaluation_rule(
    row: RunEvidenceRow,
) -> ReportMetricEvaluationRule | None:
    threshold_evaluation_order = (
        MetricClassification.BLOCKING.value,
        MetricClassification.WARNING.value,
        MetricClassification.NORMAL.value,
    )
    if (
        row.metric_direction
        == MetricDirection.LOWER_IS_BETTER.value
    ):
        return ReportMetricEvaluationRule(
            mode="threshold",
            evaluation_order=threshold_evaluation_order,
            blocking_operator=">=",
            warning_operator=">=",
            fallback_classification=(
                MetricClassification.NORMAL.value
            ),
        )
    if (
        row.metric_direction
        == MetricDirection.HIGHER_IS_BETTER.value
    ):
        return ReportMetricEvaluationRule(
            mode="threshold",
            evaluation_order=threshold_evaluation_order,
            blocking_operator="<=",
            warning_operator="<=",
            fallback_classification=(
                MetricClassification.NORMAL.value
            ),
        )
    if (
        row.metric_direction
        == MetricDirection.CONTEXT_DEPENDENT.value
    ):
        return ReportMetricEvaluationRule(
            mode="context_required",
            evaluation_order=(),
            blocking_operator=None,
            warning_operator=None,
            fallback_classification=None,
        )
    return None


def build_metric_evaluation_explanations(
    rows: Iterable[RunEvidenceRow],
) -> tuple[ReportMetricEvaluationExplanation, ...]:
    explanations: list[
        ReportMetricEvaluationExplanation
    ] = []

    for row in rows:
        if row.metric_definition_id is None:
            continue

        explanations.append(
            ReportMetricEvaluationExplanation(
                event_id=row.event_id,
                sequence_number=row.sequence_number,
                metric_definition_id=(
                    row.metric_definition_id
                ),
                metric_name=row.metric_name,
                observed_value=row.observed_value,
                unit=row.unit,
                evaluation_statistic=(
                    row.evaluation_statistic
                ),
                direction=row.metric_direction,
                evaluation_status=(
                    row.evaluation_status
                ),
                recorded_classification=(
                    row.metric_classification
                ),
                rule=_build_evaluation_rule(row),
                baseline=_build_baseline(row),
                benchmark=_build_benchmark(row),
                behaviour_profile_id=(
                    row.behaviour_profile_id
                ),
                scenario_state=row.scenario_state,
            )
        )

    return tuple(explanations)
