from dataclasses import MISSING, fields
from datetime import UTC, datetime

from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
    project_run_evidence_row,
)


def test_project_run_evidence_row_preserves_metric_evaluation_context() -> None:
    event = GeneratedEvent(
        event_id="evt-001",
        event_type="metric.observed",
        schema_version="1.0",
        event_time=datetime(
            2026,
            10,
            15,
            0,
            30,
            tzinfo=UTC,
        ),
        source_system="synthetic_observability",
        source_domain=SourceDomain.METRIC,
        scenario_id="INS-02",
        run_id="RUN0000035",
        chg_id="CHG0000031",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment=Environment.PRODUCTION,
        site_id="claims-primary",
        service_instance_id="claims-api-primary",
        sequence_number=17,
        synthetic=True,
        data={
            "metric": {
                "metric_definition_id": "request_latency",
                "name": "Request Latency",
                "observed_value": 820.0,
                "unit": "ms",
                "evaluation_statistic": "p95",
                "direction": "lower_is_better",
                "classification": "blocking",
                "evaluation_status": "evaluated",
                "baseline_profile_id": "claims_processing_nominal",
                "baseline": {
                    "metric_definition_id": "request_latency",
                    "center": 180.0,
                    "noise_stddev": 20.0,
                    "lower_bound": 100.0,
                    "upper_bound": 300.0,
                },
                "benchmark_profile_id": "business_critical_interactive",
                "effective_benchmark": {
                    "metric_definition_id": "request_latency",
                    "reference_target": 250.0,
                    "warning_threshold": 500.0,
                    "blocking_threshold": 750.0,
                    "provenance": {
                        "source_id": "synthetic-default",
                        "source_type": "synthetic_reference",
                        "source_name": "StreamOps Synthetic Default",
                        "source_reference": "streamops://benchmarks/synthetic-default",
                        "version": "1.0",
                        "retrieved_on": "2026-10-01",
                        "rationale": "Synthetic demo benchmark.",
                    },
                    "applied_overrides": [
                        "service:claims_service",
                    ],
                },
                "behaviour_profile_id": "degraded_post_change",
                "scenario_state": "degraded",
            },
        },
    )

    row = project_run_evidence_row(event)

    assert row.sequence_number == 17
    assert row.event_id == "evt-001"
    assert row.scenario_id == "INS-02"
    assert row.run_id == "RUN0000035"
    assert row.chg_id == "CHG0000031"

    assert row.business_stream == "claims"
    assert row.service == "claims_service"
    assert row.component == "claims_api"
    assert row.site_id == "claims-primary"
    assert row.service_instance_id == "claims-api-primary"

    assert row.metric_definition_id == "request_latency"
    assert row.metric_name == "Request Latency"
    assert row.observed_value == 820.0
    assert row.unit == "ms"
    assert row.evaluation_statistic == "p95"
    assert row.metric_direction == "lower_is_better"
    assert row.evaluation_status == "evaluated"
    assert row.metric_classification == "blocking"

    assert row.baseline_profile_id == "claims_processing_nominal"
    assert row.baseline_center == 180.0
    assert row.baseline_noise_stddev == 20.0
    assert row.baseline_lower_bound == 100.0
    assert row.baseline_upper_bound == 300.0

    assert row.benchmark_profile_id == "business_critical_interactive"
    assert row.benchmark_reference_target == 250.0
    assert row.benchmark_warning_threshold == 500.0
    assert row.benchmark_blocking_threshold == 750.0

    assert row.benchmark_source_id == "synthetic-default"
    assert row.benchmark_source_type == "synthetic_reference"
    assert row.benchmark_source_name == "StreamOps Synthetic Default"
    assert (
        row.benchmark_source_reference
        == "streamops://benchmarks/synthetic-default"
    )
    assert row.benchmark_source_version == "1.0"
    assert row.benchmark_source_retrieved_on == "2026-10-01"
    assert row.benchmark_source_rationale == "Synthetic demo benchmark."
    assert row.benchmark_applied_overrides == (
        "service:claims_service",
    )

    assert row.behaviour_profile_id == "degraded_post_change"
    assert row.scenario_state == "degraded"

    assert row.raw_event["event_id"] == "evt-001"
    assert row.raw_event["data"] == event.data


def test_project_run_evidence_row_preserves_capacity_context() -> None:
    event = GeneratedEvent(
        event_id="evt-capacity",
        event_type="metric.observed",
        schema_version="1.0",
        event_time=datetime(
            2026,
            10,
            15,
            0,
            31,
            tzinfo=UTC,
        ),
        source_system="synthetic_observability",
        source_domain=SourceDomain.METRIC,
        scenario_id="BANK-04",
        run_id="RUN-CAPACITY",
        chg_id=None,
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id=None,
        service_instance_id=None,
        sequence_number=8,
        synthetic=True,
        data={
            "metric": {
                "metric_definition_id": "throughput",
                "name": "Throughput",
                "observed_value": 1075.0,
                "unit": "transactions_per_second",
                "evaluation_statistic": "mean",
                "direction": "context_dependent",
                "classification": None,
                "evaluation_status": "context_required",
                "baseline_profile_id": "payment_processing_nominal",
                "baseline": {
                    "metric_definition_id": "throughput",
                    "center": 700.0,
                    "noise_stddev": 50.0,
                    "lower_bound": 500.0,
                    "upper_bound": 850.0,
                },
                "benchmark_profile_id": None,
                "effective_benchmark": None,
                "behaviour_profile_id": "capacity_saturation",
                "scenario_state": "degraded",
                "capacity": {
                    "capacity_profile_id": "critical_payment_capacity",
                    "classification": "saturated",
                    "direction": "higher_is_pressure",
                    "pressure_threshold": 900.0,
                    "saturation_threshold": 1000.0,
                },
            },
        },
    )

    row = project_run_evidence_row(event)

    assert row.metric_definition_id == "throughput"
    assert row.evaluation_status == "context_required"
    assert row.metric_classification is None
    assert row.benchmark_profile_id is None

    assert row.capacity_profile_id == "critical_payment_capacity"
    assert row.capacity_classification == "saturated"
    assert row.capacity_direction == "higher_is_pressure"
    assert row.capacity_pressure_threshold == 900.0
    assert row.capacity_saturation_threshold == 1000.0



def test_run_evidence_row_requires_raw_event() -> None:
    raw_event_field = next(
        field
        for field in fields(RunEvidenceRow)
        if field.name == "raw_event"
    )

    assert raw_event_field.default is MISSING

def test_run_evidence_row_projects_behaviour_provenance() -> None:
    from datetime import UTC, datetime

    from synthetic_ops_generator.domain.enums import (
        Environment,
        SourceDomain,
    )
    from synthetic_ops_generator.events.envelope import (
        GeneratedEvent,
    )

    event = GeneratedEvent(
        event_id="evt-behaviour-provenance",
        event_type="metric.observed",
        schema_version="1.0",
        event_time=datetime(
            2026,
            10,
            17,
            1,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_observability",
        source_domain=SourceDomain.METRIC,
        scenario_id="INS-02",
        run_id="RUN-TRACE-1C",
        behaviour_id="metric_degraded_claims_latency",
        chg_id="CHG-TRACE-1C",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment=Environment.PRODUCTION,
        site_id="claims-primary",
        service_instance_id="claims-api-primary",
        sequence_number=1,
        synthetic=True,
        data={},
    )

    row = project_run_evidence_row(event)

    assert row.behaviour_id == (
        "metric_degraded_claims_latency"
    )
    assert row.raw_event["behaviour_id"] == (
        "metric_degraded_claims_latency"
    )
