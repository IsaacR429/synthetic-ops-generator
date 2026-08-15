import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from synthetic_ops_generator.api.app import create_app

TERMINAL_STATUSES = {
    "completed",
    "failed",
    "stopped",
}


def wait_for_terminal_run(
    client: TestClient,
    run_id: str,
    *,
    timeout_seconds: float = 5.0,
) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        response = client.get(
            f"/runs/{run_id}"
        )

        assert response.status_code == 200

        payload = response.json()

        if payload["status"] in TERMINAL_STATUSES:
            return payload

        time.sleep(0.01)

    pytest.fail(
        f"Run '{run_id}' did not reach a "
        "terminal state."
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


def test_ui_can_discover_enterprises_and_scenarios(
    client: TestClient,
) -> None:
    enterprises_response = client.get(
        "/enterprises"
    )

    assert enterprises_response.status_code == 200

    enterprises = enterprises_response.json()

    enterprise_ids = {
        enterprise["enterprise_id"]
        for enterprise in enterprises
    }

    assert enterprise_ids == {
        "bank_alpha",
        "insurer_alpha",
    }

    scenarios_response = client.get(
        "/scenarios"
    )

    assert scenarios_response.status_code == 200

    scenarios = scenarios_response.json()

    scenarios_by_enterprise = {
        enterprise_id: {
            scenario["scenario_id"]
            for scenario in scenarios
            if (
                scenario["enterprise_id"]
                == enterprise_id
            )
        }
        for enterprise_id in enterprise_ids
    }

    assert scenarios_by_enterprise[
        "bank_alpha"
    ] == {
        "BANK-01",
        "BANK-02",
        "BANK-07",
    }

    assert scenarios_by_enterprise[
        "insurer_alpha"
    ] == {
        "INS-01",
        "INS-02",
    }


def test_banking_standard_ui_journey(
    client: TestClient,
) -> None:
    capabilities = client.get(
        "/scenarios/BANK-01/capabilities"
    )

    assert capabilities.status_code == 200

    capability_payload = capabilities.json()

    assert capability_payload[
        "execution_modes"
    ] == [
        "standard",
    ]

    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
            "execution_mode": "standard",
        },
    )

    assert started.status_code == 202

    started_payload = started.json()

    assert started_payload[
        "execution_mode"
    ] == "standard"

    assert started_payload[
        "historical_configuration"
    ] is None

    run_id = started_payload["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["status"] == "completed"
    assert completed["scenario_id"] == "BANK-01"
    assert completed["execution_mode"] == "standard"

    events_response = client.get(
        f"/runs/{run_id}/events"
    )

    assert events_response.status_code == 200

    events_payload = events_response.json()

    assert (
        events_payload["retained_event_count"]
        == completed["event_count"]
    )

    assert events_payload[
        "retained_event_count"
    ] > 0


def test_banking_historical_ui_journey(
    client: TestClient,
) -> None:
    capabilities = client.get(
        "/scenarios/BANK-02/capabilities"
    )

    assert capabilities.status_code == 200

    capability_payload = capabilities.json()

    assert capability_payload[
        "execution_modes"
    ] == [
        "standard",
        "historical",
    ]

    assert capability_payload[
        "historical"
    ]["supported"] is True

    assert capability_payload[
        "historical"
    ]["configuration"] == {
        "degradation_samples": 4,
        "plateau_samples": 2,
        "recovery_samples": 4,
    }

    custom_configuration = {
        "degradation_samples": 6,
        "plateau_samples": 3,
        "recovery_samples": 5,
    }

    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-02",
            "random_seed": 42,
            "execution_mode": "historical",
            "historical": custom_configuration,
        },
    )

    assert started.status_code == 202

    started_payload = started.json()

    assert (
        started_payload[
            "historical_configuration"
        ]
        == custom_configuration
    )

    run_id = started_payload["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["status"] == "completed"
    assert completed["scenario_id"] == "BANK-02"

    assert (
        completed["historical_configuration"]
        == custom_configuration
    )

    events_response = client.get(
        f"/runs/{run_id}/events"
    )

    assert events_response.status_code == 200

    events_payload = events_response.json()

    assert (
        events_payload["retained_event_count"]
        == completed["event_count"]
    )

    assert events_payload[
        "retained_event_count"
    ] > 0

    assert [
        event["sequence_number"]
        for event in events_payload["events"]
    ] == list(
        range(
            1,
            events_payload[
                "retained_event_count"
            ] + 1,
        )
    )


def test_insurance_standard_ui_journey(
    client: TestClient,
) -> None:
    capabilities = client.get(
        "/scenarios/INS-01/capabilities"
    )

    assert capabilities.status_code == 200

    assert capabilities.json()[
        "execution_modes"
    ] == [
        "standard",
    ]

    started = client.post(
        "/runs",
        json={
            "scenario_id": "INS-01",
            "random_seed": 42,
            "execution_mode": "standard",
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["status"] == "completed"
    assert completed["scenario_id"] == "INS-01"

    events = client.get(
        f"/runs/{run_id}/events"
    )

    assert events.status_code == 200

    assert (
        events.json()["retained_event_count"]
        == completed["event_count"]
    )


def test_insurance_historical_ui_journey(
    client: TestClient,
) -> None:
    capabilities = client.get(
        "/scenarios/INS-02/capabilities"
    )

    assert capabilities.status_code == 200

    assert "historical" in (
        capabilities.json()[
            "execution_modes"
        ]
    )

    custom_configuration = {
        "degradation_samples": 5,
        "plateau_samples": 1,
        "recovery_samples": 3,
    }

    started = client.post(
        "/runs",
        json={
            "scenario_id": "INS-02",
            "random_seed": 73,
            "execution_mode": "historical",
            "historical": custom_configuration,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["status"] == "completed"
    assert completed["scenario_id"] == "INS-02"

    assert (
        completed["historical_configuration"]
        == custom_configuration
    )

    events_response = client.get(
        f"/runs/{run_id}/events"
    )

    assert events_response.status_code == 200

    events_payload = events_response.json()

    assert (
        events_payload["retained_event_count"]
        == completed["event_count"]
    )

    assert events_payload[
        "retained_event_count"
    ] > 0
