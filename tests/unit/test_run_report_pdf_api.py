import io
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader

from synthetic_ops_generator.api.app import create_app
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.reporting.run_report import (
    RunReportData,
)


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
) -> dict[str, object]:
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


def extract_pdf_text(
    content: bytes,
) -> str:
    reader = PdfReader(
        io.BytesIO(content)
    )

    return "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )


def test_export_run_report_pdf_contains_real_run_evidence(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "INS-04",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["status"] == "completed"
    assert completed["event_count"] > 0

    events_response = client.get(
        f"/runs/{run_id}/events"
    )

    assert events_response.status_code == 200

    events = events_response.json()["events"]

    assert len(events) == completed["event_count"]

    scenario_response = client.get(
        "/scenarios/INS-04"
    )

    assert scenario_response.status_code == 200

    scenario = scenario_response.json()

    response = client.get(
        f"/runs/{run_id}/report.pdf"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/pdf"
    )
    assert response.headers["content-disposition"] == (
        "attachment; "
        f'filename="streamops-{run_id}-report.pdf"'
    )

    assert response.content.startswith(
        b"%PDF"
    )

    text = extract_pdf_text(
        response.content
    )

    assert "StreamOps Run Evidence Report" in text

    assert run_id in text
    assert "INS-04" in text
    assert scenario["name"] in text

    assert "Report Scope" in text
    assert "maximum_event_count" in text
    assert "total_retained_event_count" in text
    assert "included_event_count" in text

    assert "Scenario Definition" in text
    assert "Generation Behaviours" in text
    assert "Resolved Run Target" in text
    assert "Event Timeline" in text
    assert "Metric Evaluation Explanations" in text
    assert "Canonical Evidence Appendix" in text

    assert "request_latency" in text
    assert "critical_interactive_transaction" in text

    assert "warning" in text
    assert "blocking" in text

    event_ids = [
        event["event_id"]
        for event in events
    ]

    timeline_start = text.index(
        "Event Timeline"
    )
    explanations_start = text.index(
        "Metric Evaluation Explanations"
    )

    assert timeline_start < explanations_start

    timeline_text = text[
        timeline_start:explanations_start
    ]

    for event_id in event_ids:
        assert event_id in timeline_text
        assert event_id in text

    for forbidden in (
        "expected_decision",
        "expected_action",
        "expected_outcome",
        "expected_blocking_conditions",
        "expected_root_cause",
        "expected_insight",
    ):
        assert forbidden not in text


def test_export_run_report_pdf_returns_404_for_unknown_run(
    client: TestClient,
) -> None:
    response = client.get(
        "/runs/RUN9999999/report.pdf"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Run 'RUN9999999' was not found."
        )
    }



def test_export_run_report_pdf_uses_latest_250_retained_events(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "INS-04",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["status"] == "completed"

    events_response = client.get(
        f"/runs/{run_id}/events"
    )

    assert events_response.status_code == 200

    existing_events = events_response.json()["events"]

    assert existing_events

    original_event_count = len(
        existing_events
    )

    last_sequence_number = max(
        int(event["sequence_number"])
        for event in existing_events
    )

    base_time = datetime(
        2026,
        10,
        21,
        1,
        45,
        tzinfo=UTC,
    )

    boundary_events = tuple(
        GeneratedEvent(
            event_id=(
                "PDF-BOUNDARY-"
                f"{sequence_number:07d}"
            ),
            event_type="report.boundary_test",
            event_time=(
                base_time
                + timedelta(
                    seconds=offset,
                )
            ),
            source_system=(
                "synthetic_report_boundary"
            ),
            scenario_id="INS-04",
            run_id=run_id,
            sequence_number=sequence_number,
            data={
                "report_boundary_offset": offset,
            },
        )
        for offset, sequence_number in enumerate(
            range(
                last_sequence_number + 1,
                last_sequence_number + 252,
            ),
            start=1,
        )
    )

    service = (
        client.app.state.control_service
    )

    async def append_boundary_events() -> None:
        for event in boundary_events:
            await service._store.append(event)

    assert client.portal is not None

    client.portal.call(
        append_boundary_events
    )

    captured_reports: list[
        RunReportData
    ] = []

    def capture_report(
        report: RunReportData,
    ) -> bytes:
        captured_reports.append(
            report
        )
        return b"%PDF-bounded-report-test"

    monkeypatch.setattr(
        (
            "synthetic_ops_generator.api.routes.runs."
            "render_run_report_pdf"
        ),
        capture_report,
    )

    response = client.get(
        f"/runs/{run_id}/report.pdf"
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == (
        "application/pdf"
    )
    assert response.content == (
        b"%PDF-bounded-report-test"
    )

    assert len(captured_reports) == 1

    report = captured_reports[0]

    expected_total = (
        original_event_count
        + len(boundary_events)
    )

    assert (
        report.scope.total_retained_event_count
        == expected_total
    )
    assert report.scope.maximum_event_count == 250
    assert report.scope.included_event_count == 250
    assert report.scope.selection == "latest"
    assert (
        report.scope.complete_run_represented
        is False
    )

    expected_first_sequence = (
        last_sequence_number + 2
    )
    expected_last_sequence = (
        last_sequence_number + 251
    )

    assert (
        report.scope.first_sequence_number
        == expected_first_sequence
    )
    assert (
        report.scope.last_sequence_number
        == expected_last_sequence
    )

    assert len(report.evidence_rows) == 250

    assert (
        report.evidence_rows[0].sequence_number
        == expected_first_sequence
    )
    assert (
        report.evidence_rows[-1].sequence_number
        == expected_last_sequence
    )

    included_event_ids = {
        row.event_id
        for row in report.evidence_rows
    }

    # The first of the 251 newly appended events is outside
    # the latest-250 window.
    assert (
        boundary_events[0].event_id
        not in included_event_ids
    )

    assert (
        boundary_events[1].event_id
        in included_event_ids
    )

    assert (
        boundary_events[-1].event_id
        in included_event_ids
    )
