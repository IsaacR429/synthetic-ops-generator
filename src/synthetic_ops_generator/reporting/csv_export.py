from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable
from datetime import datetime
from typing import Any

from synthetic_ops_generator.reporting.evidence_row import (
    RunEvidenceRow,
)

RUN_EVIDENCE_CSV_COLUMNS = (
    "sequence_number",
    "event_time",
    "event_id",
    "event_type",
    "schema_version",
    "source_system",
    "source_domain",
    "scenario_id",
    "run_id",
    "behaviour_id",
    "chg_id",
    "business_stream",
    "service",
    "component",
    "environment",
    "site_id",
    "service_instance_id",
    "synthetic",
    "check_definition_id",
    "operational_test_id",
    "operational_test_category",
    "operational_test_type",
    "operational_test_status",
    "operational_test_result",
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


def _json_text(
    value: Any,
) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _datetime_text(
    value: datetime,
) -> str:
    text = value.isoformat()

    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"

    return text


def _cell_text(
    value: object,
) -> str:
    if value is None:
        return ""

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, datetime):
        return _datetime_text(value)

    if isinstance(value, tuple):
        return _json_text(list(value))

    if isinstance(value, (dict, list)):
        return _json_text(value)

    return str(value)


def _row_mapping(
    row: RunEvidenceRow,
) -> dict[str, str]:
    values: dict[str, str] = {}

    for column in RUN_EVIDENCE_CSV_COLUMNS:
        if column == "raw_event_json":
            value: object = row.raw_event
        else:
            value = getattr(row, column)

        values[column] = _cell_text(value)

    return values


def serialize_run_evidence_csv(
    rows: Iterable[RunEvidenceRow],
) -> str:
    output = io.StringIO(newline="")

    writer = csv.DictWriter(
        output,
        fieldnames=RUN_EVIDENCE_CSV_COLUMNS,
        lineterminator="\n",
        extrasaction="raise",
    )

    writer.writeheader()

    for row in rows:
        writer.writerow(
            _row_mapping(row)
        )

    return output.getvalue()
