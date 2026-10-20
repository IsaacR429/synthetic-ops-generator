import csv
import io
import json
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from synthetic_ops_generator.api.app import create_app


SCENARIO_IDS = (
    "BANK-01",
    "BANK-02",
    "BANK-03",
    "BANK-04",
    "BANK-05",
    "BANK-06",
    "BANK-07",
    "INS-01",
    "INS-02",
    "INS-03",
    "INS-04",
    "INS-05",
    "INS-06",
)

FORBIDDEN_ORACLE_FIELDS = {
    "expected_decision",
    "expected_action",
    "expected_outcome",
    "expected_blocking_conditions",
    "expected_root_cause",
    "expected_insight",
}


@pytest.fixture
def client(
    tmp_path: Path,
) -> Iterator[TestClient]:
    app = create_app(
        data_root=tmp_path / "runs"
    )

    with TestClient(app) as test_client:
        yield test_client


def wait_for_terminal_run(
    client: TestClient,
    run_id: str,
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, Any]:
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while True:
        response = client.get(
            f"/runs/{run_id}"
        )

        assert response.status_code == 200

        payload = response.json()

        if payload["status"] in {
            "completed",
            "failed",
            "stopped",
        }:
            return payload

        if time.monotonic() >= deadline:
            raise AssertionError(
                f"Run '{run_id}' did not reach "
                "a terminal state within "
                f"{timeout_seconds} seconds."
            )

        time.sleep(0.01)


def parse_timestamp(
    value: str,
) -> datetime:
    return datetime.fromisoformat(
        value.replace(
            "Z",
            "+00:00",
        )
    )


def nullable_csv(
    value: str,
) -> str | None:
    return value if value != "" else None


def find_forbidden_keys(
    value: object,
    *,
    path: str = "$",
) -> list[str]:
    findings: list[str] = []

    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"

            if key in FORBIDDEN_ORACLE_FIELDS:
                findings.append(child_path)

            findings.extend(
                find_forbidden_keys(
                    child,
                    path=child_path,
                )
            )

    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(
                find_forbidden_keys(
                    child,
                    path=f"{path}[{index}]",
                )
            )

    return findings


def test_public_catalogue_exposes_all_bank_and_insurance_scenarios(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios"
    )

    assert response.status_code == 200

    scenarios = response.json()

    assert tuple(
        scenario["scenario_id"]
        for scenario in scenarios
    ) == SCENARIO_IDS


@pytest.mark.parametrize(
    "scenario_id",
    SCENARIO_IDS,
)
def test_catalogue_scenario_runtime_and_csv_export_are_faithful(
    client: TestClient,
    scenario_id: str,
) -> None:
    started_response = client.post(
        "/runs",
        json={
            "scenario_id": scenario_id,
            "random_seed": 42,
        },
    )

    assert started_response.status_code == 202

    started = started_response.json()

    assert started["scenario_id"] == scenario_id

    run_id = started["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["scenario_id"] == scenario_id
    assert completed["run_id"] == run_id
    assert completed["status"] == "completed"
    assert completed["current_state"] == "completed"
    assert completed["validation_passed"] is True
    assert completed["error_message"] is None
    assert completed["event_count"] > 0

    events_response = client.get(
        f"/runs/{run_id}/events"
    )

    assert events_response.status_code == 200

    event_payload = events_response.json()

    assert event_payload["run_id"] == run_id
    assert (
        event_payload["retained_event_count"]
        == completed["event_count"]
    )
    assert (
        event_payload["returned_event_count"]
        == completed["event_count"]
    )

    events = event_payload["events"]

    assert len(events) == completed["event_count"]

    sequence_numbers = [
        event["sequence_number"]
        for event in events
    ]

    assert sequence_numbers == list(
        range(
            1,
            len(events) + 1,
        )
    )

    event_ids = [
        event["event_id"]
        for event in events
    ]

    assert len(event_ids) == len(set(event_ids))

    assert {
        event["scenario_id"]
        for event in events
    } == {
        scenario_id
    }

    assert {
        event["run_id"]
        for event in events
    } == {
        run_id
    }

    assert {
        event["chg_id"]
        for event in events
    } == {
        completed["change_id"]
    }

    event_times = [
        parse_timestamp(
            event["event_time"]
        )
        for event in events
    ]

    assert event_times == sorted(event_times)

    oracle_leaks = []

    for event in events:
        oracle_leaks.extend(
            find_forbidden_keys(
                event,
                path=(
                    f"$event[{event['sequence_number']}]"
                ),
            )
        )

    assert oracle_leaks == []

    export_response = client.get(
        f"/runs/{run_id}/export.csv"
    )

    assert export_response.status_code == 200
    assert export_response.headers[
        "content-type"
    ] == "text/csv; charset=utf-8"
    assert export_response.headers[
        "content-disposition"
    ] == (
        "attachment; "
        f'filename="streamops-{run_id}-events.csv"'
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                export_response.text
            )
        )
    )

    assert len(rows) == completed["event_count"]

    assert [
        int(row["sequence_number"])
        for row in rows
    ] == sequence_numbers

    assert [
        row["event_id"]
        for row in rows
    ] == event_ids

    assert len(
        {
            row["event_id"]
            for row in rows
        }
    ) == len(rows)

    for event, row in zip(
        events,
        rows,
        strict=True,
    ):
        assert row["event_id"] == event["event_id"]
        assert row["event_type"] == event["event_type"]
        assert (
            row["schema_version"]
            == event["schema_version"]
        )
        assert (
            row["source_system"]
            == event["source_system"]
        )
        assert (
            nullable_csv(
                row["source_domain"]
            )
            == event["source_domain"]
        )
        assert row["scenario_id"] == scenario_id
        assert row["run_id"] == run_id
        assert (
            nullable_csv(
                row["behaviour_id"]
            )
            == event.get("behaviour_id")
        )
        assert (
            nullable_csv(
                row["chg_id"]
            )
            == event["chg_id"]
        )
        assert (
            nullable_csv(
                row["business_stream"]
            )
            == event["business_stream"]
        )
        assert (
            nullable_csv(
                row["service"]
            )
            == event["service"]
        )
        assert (
            nullable_csv(
                row["component"]
            )
            == event["component"]
        )
        assert (
            nullable_csv(
                row["environment"]
            )
            == event["environment"]
        )
        assert (
            nullable_csv(
                row["site_id"]
            )
            == event["site_id"]
        )
        assert (
            nullable_csv(
                row["service_instance_id"]
            )
            == event["service_instance_id"]
        )

        assert (
            parse_timestamp(
                row["event_time"]
            )
            == parse_timestamp(
                event["event_time"]
            )
        )

        assert row["synthetic"] == (
            "true"
            if event["synthetic"]
            else "false"
        )

        raw_event = json.loads(
            row["raw_event_json"]
        )

        assert raw_event == event

        assert find_forbidden_keys(
            raw_event
        ) == []
