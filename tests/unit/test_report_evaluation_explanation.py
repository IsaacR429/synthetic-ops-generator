from datetime import UTC, datetime

from synthetic_ops_generator.reporting.evaluation_explanation import (
    build_metric_evaluation_explanations,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
)


def _metric_row(
    **overrides,
) -> RunEvidenceRow:
    values = {
        "sequence_number": 17,
        "event_time": datetime(
            2026,
            10,
            15,
            8,
            1,
            tzinfo=UTC,
        ),
        "event_id": "evt-metric-017",
        "event_type": "metric.observed",
        "schema_version": "1.0",
        "source_system": "synthetic_observability",
        "source_domain": "metric",
        "scenario_id": "INS-02",
        "run_id": "RUN-REPORT-002",
        "chg_id": "CHG-REPORT-002",
        "business_stream": "claims",
        "service": "claims_service",
        "component": "claims_api",
        "environment": "production",
        "site_id": "claims-primary",
        "service_instance_id": "claims-api-primary",
        "synthetic": True,
        "raw_event": {
            "event_id": "evt-metric-017",
        },
        "metric_definition_id": "request_latency",
        "metric_name": "Request Latency",
        "observed_value": 820.0,
        "unit": "ms",
        "evaluation_statistic": "p95",
        "metric_direction": "lower_is_better",
        "evaluation_status": "evaluated",
        "metric_classification": "blocking",
        "baseline_profile_id": "claims_nominal",
        "baseline_center": 210.0,
        "baseline_noise_stddev": 18.0,
        "baseline_lower_bound": 150.0,
        "baseline_upper_bound": 280.0,
        "benchmark_profile_id": "claims_latency_policy",
        "benchmark_reference_target": 250.0,
        "benchmark_warning_threshold": 500.0,
        "benchmark_blocking_threshold": 750.0,
        "benchmark_source_id": "src-claims-slo",
        "benchmark_source_type": "policy",
        "benchmark_source_name": "Claims Service SLO",
        "benchmark_source_reference": "SLO-CLAIMS-001",
        "benchmark_source_version": "3",
        "benchmark_source_retrieved_on": "2026-10-01",
        "benchmark_source_rationale": (
            "Approved service latency objective."
        ),
        "benchmark_applied_overrides": (
            "production",
            "critical_service",
        ),
        "behaviour_profile_id": "claims_degraded",
        "scenario_state": "degraded",
    }

    values.update(overrides)

    return RunEvidenceRow(**values)


def test_metric_evaluation_explanation_preserves_recorded_context() -> None:
    row = _metric_row()

    explanations = build_metric_evaluation_explanations(
        (row,)
    )

    assert len(explanations) == 1

    explanation = explanations[0]

    assert explanation.event_id == row.event_id
    assert (
        explanation.sequence_number
        == row.sequence_number
    )

    assert (
        explanation.metric_definition_id
        == "request_latency"
    )
    assert explanation.metric_name == "Request Latency"
    assert explanation.observed_value == 820.0
    assert explanation.unit == "ms"
    assert explanation.evaluation_statistic == "p95"

    assert explanation.direction == "lower_is_better"
    assert explanation.evaluation_status == "evaluated"

    # This is recorded StreamOps truth, not a report calculation.
    assert (
        explanation.recorded_classification
        == "blocking"
    )

    assert explanation.baseline is not None
    assert (
        explanation.baseline.profile_id
        == "claims_nominal"
    )
    assert explanation.baseline.center == 210.0
    assert explanation.baseline.noise_stddev == 18.0
    assert explanation.baseline.lower_bound == 150.0
    assert explanation.baseline.upper_bound == 280.0

    assert explanation.benchmark is not None
    assert (
        explanation.benchmark.profile_id
        == "claims_latency_policy"
    )
    assert (
        explanation.benchmark.reference_target
        == 250.0
    )
    assert (
        explanation.benchmark.warning_threshold
        == 500.0
    )
    assert (
        explanation.benchmark.blocking_threshold
        == 750.0
    )
    assert explanation.benchmark.applied_overrides == (
        "production",
        "critical_service",
    )

    provenance = explanation.benchmark.provenance

    assert provenance is not None
    assert provenance.source_id == "src-claims-slo"
    assert provenance.source_type == "policy"
    assert (
        provenance.source_name
        == "Claims Service SLO"
    )
    assert (
        provenance.source_reference
        == "SLO-CLAIMS-001"
    )
    assert provenance.version == "3"
    assert provenance.retrieved_on == "2026-10-01"
    assert provenance.rationale == (
        "Approved service latency objective."
    )

    assert (
        explanation.behaviour_profile_id
        == "claims_degraded"
    )
    assert explanation.scenario_state == "degraded"


def test_context_required_metric_preserves_absence_of_benchmark_truth() -> None:
    row = _metric_row(
        metric_direction="context_dependent",
        evaluation_status="context_required",
        metric_classification=None,
        benchmark_profile_id=None,
        benchmark_reference_target=None,
        benchmark_warning_threshold=None,
        benchmark_blocking_threshold=None,
        benchmark_source_id=None,
        benchmark_source_type=None,
        benchmark_source_name=None,
        benchmark_source_reference=None,
        benchmark_source_version=None,
        benchmark_source_retrieved_on=None,
        benchmark_source_rationale=None,
        benchmark_applied_overrides=(),
    )

    explanations = build_metric_evaluation_explanations(
        (row,)
    )

    assert len(explanations) == 1

    explanation = explanations[0]

    assert (
        explanation.evaluation_status
        == "context_required"
    )
    assert explanation.recorded_classification is None
    assert explanation.benchmark is None


def test_non_metric_evidence_is_not_given_metric_explanation() -> None:
    row = _metric_row(
        event_type="deployment.completed",
        source_domain="deployment",
        metric_definition_id=None,
        metric_name=None,
        observed_value=None,
        unit=None,
        evaluation_statistic=None,
        metric_direction=None,
        evaluation_status=None,
        metric_classification=None,
        baseline_profile_id=None,
        baseline_center=None,
        baseline_noise_stddev=None,
        baseline_lower_bound=None,
        baseline_upper_bound=None,
        benchmark_profile_id=None,
        benchmark_reference_target=None,
        benchmark_warning_threshold=None,
        benchmark_blocking_threshold=None,
        benchmark_source_id=None,
        benchmark_source_type=None,
        benchmark_source_name=None,
        benchmark_source_reference=None,
        benchmark_source_version=None,
        benchmark_source_retrieved_on=None,
        benchmark_source_rationale=None,
        benchmark_applied_overrides=(),
    )

    assert build_metric_evaluation_explanations(
        (row,)
    ) == ()
