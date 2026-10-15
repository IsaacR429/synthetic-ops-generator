import csv
import io
import json
from datetime import UTC, datetime

from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.reporting.csv_export import (
    RUN_EVIDENCE_CSV_COLUMNS,
    serialize_run_evidence_csv,
)
from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
    project_run_evidence_row,
)

EXPECTED_COLUMNS = (
    "sequence_number",
    "event_time",
    "event_id",
    "event_type",
    "schema_version",
    "source_system",
    "source_domain",
    "scenario_id",
    "run_id",
    "chg_id",
    "business_stream",
    "service",
    "component",
    "environment",
    "site_id",
    "service_instance_id",
    "synthetic",
    "metric_definition_id",
    "metric_name",
    "observed_value",
    "unit",
    "evaluation_statistic",
    "metric_direction",
    "evaluation_status",
    "metric_classification",
    "baseline_profile_id",
    "baseline_center",
    "baseline_noise_stddev",
    "baseline_lower_bound",
    "baseline_upper_bound",
    "benchmark_profile_id",
    "benchmark_reference_target",
    "benchmark_warning_threshold",
    "benchmark_blocking_threshold",
    "benchmark_source_id",
    "benchmark_source_type",
    "benchmark_source_name",
    "benchmark_source_reference",
    "benchmark_source_version",
    "benchmark_source_retrieved_on",
    "benchmark_source_rationale",
    "benchmark_applied_overrides",
    "behaviour_profile_id",
    "scenario_state",
    "historical_counterfactual_value",
    "historical_perturbation_strength",
    "historical_perturbation_phase",
    "capacity_profile_id",
    "capacity_classification",
    "capacity_direction",
    "capacity_pressure_threshold",
    "capacity_saturation_threshold",
    "raw_event_json",
)


def make_row(
    *,
    sequence_number: int,
    event_id: str,
) -> RunEvidenceRow:
    return RunEvidenceRow(
        sequence_number=sequence_number,
        event_time=datetime(
            2026,
            10,
            15,
            0,
            30,
            sequence_number,
            tzinfo=UTC,
        ),
        event_id=event_id,
        event_type="metric.observed",
        schema_version="1.0",
        source_system="synthetic_observability",
        source_domain="metric",
        scenario_id="INS-02",
        run_id="RUN0000035",
        chg_id="CHG0000031",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment="production",
        site_id="claims-primary",
        service_instance_id="claims-api-primary",
        synthetic=True,
        raw_event={
            "z": 2,
            "event_id": event_id,
            "a": {
                "value": "quoted, value",
            },
        },
    )


def test_csv_contract_has_stable_columns_and_serializes_metric_context() -> None:
    row = make_row(
        sequence_number=17,
        event_id="evt-001",
    )

    row = RunEvidenceRow(
        **{
            **row.__dict__,
            "metric_definition_id": "request_latency",
            "metric_name": 'Request, "Latency"\nP95',
            "observed_value": 820.0,
            "unit": "ms",
            "evaluation_statistic": "p95",
            "metric_direction": "lower_is_better",
            "evaluation_status": "evaluated",
            "metric_classification": "blocking",
            "baseline_profile_id": "claims_processing_nominal",
            "baseline_center": 180.0,
            "baseline_noise_stddev": 20.0,
            "baseline_lower_bound": 100.0,
            "baseline_upper_bound": 300.0,
            "benchmark_profile_id": "business_critical_interactive",
            "benchmark_reference_target": 250.0,
            "benchmark_warning_threshold": 500.0,
            "benchmark_blocking_threshold": 750.0,
            "benchmark_source_id": "synthetic-default",
            "benchmark_source_type": "synthetic_reference",
            "benchmark_source_name": "StreamOps Synthetic Default",
            "benchmark_source_reference": (
                "streamops://benchmarks/synthetic-default"
            ),
            "benchmark_source_version": "1.0",
            "benchmark_source_retrieved_on": "2026-10-01",
            "benchmark_source_rationale": (
                "Synthetic demo benchmark."
            ),
            "benchmark_applied_overrides": (
                "scenario:INS-02",
                "service:claims_service",
            ),
            "behaviour_profile_id": "degraded_post_change",
            "scenario_state": "degraded",
        }
    )

    text = serialize_run_evidence_csv([row])

    assert RUN_EVIDENCE_CSV_COLUMNS == EXPECTED_COLUMNS
    assert "\r" not in text

    reader = csv.DictReader(io.StringIO(text))
    assert tuple(reader.fieldnames or ()) == EXPECTED_COLUMNS

    records = list(reader)
    assert len(records) == 1

    record = records[0]

    assert record["sequence_number"] == "17"
    assert record["event_time"] == "2026-10-15T00:30:17Z"
    assert record["synthetic"] == "true"

    assert record["metric_definition_id"] == "request_latency"
    assert record["metric_name"] == 'Request, "Latency"\nP95'
    assert record["observed_value"] == "820.0"

    assert record["benchmark_applied_overrides"] == (
        '["scenario:INS-02","service:claims_service"]'
    )

    assert record["raw_event_json"] == json.dumps(
        row.raw_event,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def test_csv_preserves_input_order_and_serializes_missing_values_as_blank() -> None:
    first = make_row(
        sequence_number=2,
        event_id="evt-002",
    )
    second = make_row(
        sequence_number=1,
        event_id="evt-001",
    )

    text = serialize_run_evidence_csv(
        [
            first,
            second,
        ]
    )

    records = list(
        csv.DictReader(
            io.StringIO(text)
        )
    )

    assert [
        record["event_id"]
        for record in records
    ] == [
        "evt-002",
        "evt-001",
    ]

    assert records[0]["metric_definition_id"] == ""
    assert records[0]["benchmark_profile_id"] == ""
    assert records[0]["capacity_profile_id"] == ""
    assert records[0]["chg_id"] == "CHG0000031"



def test_csv_preserves_unknown_future_scenario_payload() -> None:
    event = GeneratedEvent(
        event_id="evt-future-insurance",
        event_type="insurance.future_signal",
        schema_version="1.0",
        event_time=datetime(
            2026,
            10,
            15,
            1,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_future_provider",
        source_domain=SourceDomain.EVIDENCE,
        scenario_id="INS-FUTURE",
        run_id="RUN-FUTURE",
        chg_id=None,
        business_stream="claims",
        service="future_claims_service",
        component="future_component",
        environment=Environment.PRODUCTION,
        site_id=None,
        service_instance_id=None,
        sequence_number=1,
        synthetic=True,
        data={
            "future_domain": {
                "new_field": "new-value",
                "nested": {
                    "confidence": 0.93,
                },
            },
        },
    )

    row = project_run_evidence_row(event)

    text = serialize_run_evidence_csv([row])

    record = next(
        csv.DictReader(
            io.StringIO(text)
        )
    )

    assert record["scenario_id"] == "INS-FUTURE"
    assert record["event_type"] == "insurance.future_signal"

    raw_event = json.loads(
        record["raw_event_json"]
    )

    assert raw_event["data"]["future_domain"] == {
        "new_field": "new-value",
        "nested": {
            "confidence": 0.93,
        },
    }

    assert record["metric_definition_id"] == ""
    assert record["capacity_profile_id"] == ""
