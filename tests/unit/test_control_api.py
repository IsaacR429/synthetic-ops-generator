import time
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from synthetic_ops_generator.api.app import create_app
from synthetic_ops_generator.control.models import (
    RunStatus,
    StopRunResult,
)
from synthetic_ops_generator.control.service import (
    RunNotFoundError,
    RunNotReplayableError,
    RunNotStoppableError,
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
    timeout_seconds: float = 5.0,
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


def test_health_endpoint_returns_ok(
    client: TestClient,
) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "synthetic-ops-generator",
    }


def test_list_scenarios_returns_catalogue(
    client: TestClient,
) -> None:
    response = client.get("/scenarios")

    assert response.status_code == 200

    payload = response.json()

    assert [
        scenario["scenario_id"]
        for scenario in payload
    ] == [
        "BANK-01",
        "BANK-02",
        "BANK-07",
        "INS-01",
        "INS-02",
    ]

    assert (
        payload[0]["name"]
        == "Successful Payment Release"
    )
    assert payload[0]["industry"] == "banking"
    assert (
        payload[0]["enterprise_id"]
        == "bank_alpha"
    )
    assert (
        payload[0]["environment"]
        == "production"
    )


def test_get_scenario_returns_full_definition(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/BANK-01"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["scenario_id"] == "BANK-01"
    assert (
        payload["name"]
        == "Successful Payment Release"
    )

    assert (
        payload["target"]["enterprise_id"]
        == "bank_alpha"
    )
    assert (
        payload["target"]["business_stream_id"]
        == "payments"
    )
    assert (
        payload["target"]["service_id"]
        == "payment_service"
    )

    assert (
        payload["trigger"]["source"]
        == "deployment"
    )
    assert (
        payload["trigger"]["artifact"]
        == "payment-api"
    )
    assert (
        payload["trigger"]["version"]
        == "2.5.0"
    )

    assert (
        payload["expected_result"][
            "expected_decision"
        ]
        == "pass"
    )
    assert (
        payload["expected_result"][
            "expected_action"
        ]
        == "proceed"
    )
    assert (
        payload["expected_result"][
            "expected_outcome"
        ]
        == "successful"
    )


def test_get_unknown_scenario_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/UNKNOWN"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Scenario 'UNKNOWN' was not found."
        )
    }


def test_start_run_executes_scenario(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert response.status_code == 202

    payload = response.json()

    assert payload == {
        "scenario_id": "BANK-01",
        "run_id": "RUN0000001",
        "change_id": "CHG0000001",
        "status": "running",
        "execution_mode": "standard",
        "generation_lifecycle": "bounded",
        "historical_configuration": None,
        "continuous_configuration": None,
    }


def test_start_continuous_run_executes_scenario(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
            "generation_lifecycle": "continuous",
        },
    )

    assert response.status_code == 202

    payload = response.json()

    assert payload == {
        "scenario_id": "BANK-01",
        "run_id": "RUN0000001",
        "change_id": "CHG0000001",
        "status": "running",
        "execution_mode": "standard",
        "generation_lifecycle": "continuous",
        "historical_configuration": None,
        "continuous_configuration": {
            "stop_mode": "manual",
            "duration_seconds": None,
        },
    }

    stop_response = client.post(
        f"/runs/{payload['run_id']}/stop"
    )

    assert stop_response.status_code == 200

    stopped = stop_response.json()

    assert stopped["run_id"] == payload["run_id"]
    assert stopped["scenario_id"] == "BANK-01"
    assert stopped["status"] == "stopped"
    assert stopped["event_count"] >= 0


def test_get_continuous_run_returns_lifecycle_configuration(
    client: TestClient,
) -> None:
    started_response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
            "generation_lifecycle": "continuous",
        },
    )

    assert started_response.status_code == 202

    started = started_response.json()
    run_id = started["run_id"]

    response = client.get(
        f"/runs/{run_id}"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["generation_lifecycle"]
        == "continuous"
    )

    assert payload["continuous_configuration"] == {
        "stop_mode": "manual",
        "duration_seconds": None,
    }

    assert payload["historical_configuration"] is None

    stop_response = client.post(
        f"/runs/{run_id}/stop"
    )

    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"


def test_list_running_runs_tracks_continuous_run(
    client: TestClient,
) -> None:
    started_response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
            "generation_lifecycle": "continuous",
        },
    )

    assert started_response.status_code == 202

    run_id = started_response.json()["run_id"]

    running_response = client.get(
        "/runs?status=running"
    )

    assert running_response.status_code == 200

    running_runs = running_response.json()

    matching_run = next(
        (
            run
            for run in running_runs
            if run["run_id"] == run_id
        ),
        None,
    )

    assert matching_run is not None
    assert matching_run["status"] == "running"
    assert (
        matching_run["generation_lifecycle"]
        == "continuous"
    )
    assert matching_run[
        "continuous_configuration"
    ] == {
        "stop_mode": "manual",
        "duration_seconds": None,
    }

    stop_response = client.post(
        f"/runs/{run_id}/stop"
    )

    assert stop_response.status_code == 200

    running_after_stop_response = client.get(
        "/runs?status=running"
    )

    assert (
        running_after_stop_response.status_code
        == 200
    )

    running_after_stop = (
        running_after_stop_response.json()
    )

    assert all(
        run["run_id"] != run_id
        for run in running_after_stop
    )


def test_list_runs_returns_persisted_catalogue(
    client: TestClient,
) -> None:
    completed_response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert completed_response.status_code == 202

    completed_run_id = (
        completed_response.json()["run_id"]
    )

    completed = wait_for_terminal_run(
        client,
        completed_run_id,
    )

    assert completed["status"] == "completed"

    continuous_response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 43,
            "generation_lifecycle": "continuous",
        },
    )

    assert continuous_response.status_code == 202

    continuous_run_id = (
        continuous_response.json()["run_id"]
    )

    stop_response = client.post(
        f"/runs/{continuous_run_id}/stop"
    )

    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    catalogue_response = client.get(
        "/runs"
    )

    assert catalogue_response.status_code == 200

    catalogue = catalogue_response.json()

    assert [
        run["run_id"]
        for run in catalogue
    ] == [
        continuous_run_id,
        completed_run_id,
    ]

    assert [
        run["status"]
        for run in catalogue
    ] == [
        "stopped",
        "completed",
    ]

    assert all(
        run["target"]
        == {
            "enterprise_id": "bank_alpha",
            "business_stream_id": "payments",
            "service_id": "payment_service",
            "component_ids": [
                "payment_api",
                "payment_database",
                "payment_worker",
            ],
            "environment": "production",
        }
        for run in catalogue
    )


def test_start_bounded_run_rejects_continuous_configuration(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "generation_lifecycle": "bounded",
            "continuous": {
                "stop_mode": "manual",
            },
        },
    )

    assert response.status_code == 422

    assert (
        "Continuous configuration can only "
        "be supplied for continuous generation."
        in response.text
    )


def test_start_continuous_historical_run_is_rejected(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "execution_mode": "historical",
            "generation_lifecycle": "continuous",
        },
    )

    assert response.status_code == 422

    assert (
        "Continuous lifecycle is not supported "
        "for historical execution."
        in response.text
    )


def test_start_continuous_manual_run_rejects_duration(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "generation_lifecycle": "continuous",
            "continuous": {
                "stop_mode": "manual",
                "duration_seconds": 30,
            },
        },
    )

    assert response.status_code == 422

    assert (
        "Manual continuous execution "
        "cannot define a duration."
        in response.text
    )


def test_start_duration_continuous_run_returns_409(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "generation_lifecycle": "continuous",
            "continuous": {
                "stop_mode": "duration",
                "duration_seconds": 30,
            },
        },
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Duration-based continuous "
            "execution is not supported yet."
        )
    }


def test_start_run_uses_shared_identifiers(
    client: TestClient,
) -> None:
    first = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    second = client.post(
        "/runs",
        json={
            "scenario_id": "INS-01",
            "random_seed": 42,
        },
    )

    assert first.status_code == 202
    assert second.status_code == 202

    assert (
        first.json()["run_id"]
        == "RUN0000001"
    )
    assert (
        second.json()["run_id"]
        == "RUN0000002"
    )

    assert (
        first.json()["change_id"]
        == "CHG0000001"
    )
    assert (
        second.json()["change_id"]
        == "CHG0000002"
    )


def test_start_run_returns_404_for_unknown_scenario(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "UNKNOWN",
            "random_seed": 42,
        },
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Scenario 'UNKNOWN' was not found."
        )
    }


def test_get_run_returns_persisted_metadata(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    payload = wait_for_terminal_run(
        client,
        run_id,
    )

    assert payload["run_id"] == run_id
    assert payload["scenario_id"] == "BANK-01"
    assert payload["change_id"] == "CHG0000001"

    assert payload["status"] == "completed"
    assert payload["current_state"] == "completed"

    assert payload["event_count"] == 32
    assert payload["validation_passed"] is True

    assert payload["random_seed"] == 42
    assert payload["event_interval_seconds"] == 5.0

    assert payload["target"] == {
        "enterprise_id": "bank_alpha",
        "business_stream_id": "payments",
        "service_id": "payment_service",
        "component_ids": [
            "payment_api",
            "payment_database",
            "payment_worker",
        ],
        "environment": "production",
    }

    assert payload["started_at"] is not None
    assert payload["completed_at"] is not None
    assert payload["error_message"] is None


def test_get_unknown_run_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/runs/RUN9999999"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Run 'RUN9999999' was not found."
        )
    }


def test_replay_run_republishes_retained_events(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
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

    replayed = client.post(
        f"/runs/{run_id}/replay"
    )

    assert replayed.status_code == 200

    assert replayed.json() == {
        "run_id": run_id,
        "scenario_id": "BANK-01",
        "replayed_event_count": 32,
    }


def test_replay_unknown_run_returns_404(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs/RUN9999999/replay"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": (
            "Run 'RUN9999999' was not found."
        )
    }


def test_replay_running_run_returns_409(
    client: TestClient,
) -> None:
    service = (
        client.app.state.control_service
    )

    service.replay_run = AsyncMock(
        side_effect=RunNotReplayableError(
            "Run 'RUN0000001' cannot be "
            "replayed while it is running."
        )
    )

    response = client.post(
        "/runs/RUN0000001/replay"
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": (
            "Run 'RUN0000001' cannot be "
            "replayed while it is running."
        )
    }


def test_stop_run_returns_stopped_response(
    client: TestClient,
) -> None:
    service = (
        client.app.state.control_service
    )

    service.stop_run = AsyncMock(
        return_value=StopRunResult(
            run_id="RUN0000001",
            scenario_id="BANK-01",
            status=RunStatus.STOPPED,
            event_count=7,
        )
    )

    response = client.post(
        "/runs/RUN0000001/stop"
    )

    assert response.status_code == 200

    assert response.json() == {
        "run_id": "RUN0000001",
        "scenario_id": "BANK-01",
        "status": "stopped",
        "event_count": 7,
    }


def test_stop_unknown_run_returns_404(
    client: TestClient,
) -> None:
    service = (
        client.app.state.control_service
    )

    service.stop_run = AsyncMock(
        side_effect=RunNotFoundError(
            "Run 'RUN9999999' was not found."
        )
    )

    response = client.post(
        "/runs/RUN9999999/stop"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Run 'RUN9999999' "
            "was not found."
        )
    }


def test_stop_non_stoppable_run_returns_409(
    client: TestClient,
) -> None:
    service = (
        client.app.state.control_service
    )

    service.stop_run = AsyncMock(
        side_effect=RunNotStoppableError(
            "Run 'RUN0000001' cannot be "
            "stopped because its status "
            "is 'completed'."
        )
    )

    response = client.post(
        "/runs/RUN0000001/stop"
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Run 'RUN0000001' cannot be "
            "stopped because its status "
            "is 'completed'."
        )
    }


def test_start_historical_run_executes_scenario(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-02",
            "random_seed": 42,
            "execution_mode": "historical",
        },
    )

    assert response.status_code == 202

    payload = response.json()

    assert payload == {
        "scenario_id": "BANK-02",
        "run_id": "RUN0000001",
        "change_id": "CHG0000001",
        "status": "running",
        "execution_mode": "historical",
        "generation_lifecycle": "bounded",
        "historical_configuration": {
            "degradation_samples": 4,
            "plateau_samples": 2,
            "recovery_samples": 4,
        },
        "continuous_configuration": None,
    }

    completed = wait_for_terminal_run(
        client,
        payload["run_id"],
    )

    assert (
        completed["status"]
        == "completed"
    )

    assert (
        completed["current_state"]
        == "completed"
    )

    assert (
        completed["execution_mode"]
        == "historical"
    )

    assert completed["event_count"] == 48

    assert (
        completed["validation_passed"]
        is None
    )

    assert completed["error_message"] is None


def test_list_enterprises_returns_catalogue(
    client: TestClient,
) -> None:
    response = client.get(
        "/enterprises"
    )

    assert response.status_code == 200

    payload = response.json()

    assert [
        enterprise["enterprise_id"]
        for enterprise in payload
    ] == [
        "bank_alpha",
        "insurer_alpha",
    ]

    assert [
        enterprise["industry"]
        for enterprise in payload
    ] == [
        "banking",
        "insurance",
    ]

    assert all(
        enterprise[
            "business_stream_count"
        ] > 0
        for enterprise in payload
    )

    assert all(
        enterprise["service_count"] > 0
        for enterprise in payload
    )

    assert all(
        enterprise["component_count"] > 0
        for enterprise in payload
    )


def test_get_enterprise_returns_operational_structure(
    client: TestClient,
) -> None:
    response = client.get(
        "/enterprises/bank_alpha"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["enterprise_id"]
        == "bank_alpha"
    )

    assert payload["industry"] == "banking"

    assert payload["business_streams"]
    assert payload["services"]
    assert payload["components"]

    assert any(
        service["service_id"]
        == "payment_service"
        for service in payload["services"]
    )

    assert any(
        component["component_id"]
        == "payment_api"
        for component
        in payload["components"]
    )


def test_get_insurance_enterprise_uses_same_contract(
    client: TestClient,
) -> None:
    response = client.get(
        "/enterprises/insurer_alpha"
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        payload["enterprise_id"]
        == "insurer_alpha"
    )

    assert payload["industry"] == "insurance"

    assert any(
        service["service_id"]
        == "claims_service"
        for service in payload["services"]
    )

    assert any(
        component["component_id"]
        == "claims_api"
        for component
        in payload["components"]
    )


def test_get_unknown_enterprise_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/enterprises/UNKNOWN"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Enterprise 'UNKNOWN' "
            "was not found."
        )
    }


def test_get_historical_scenario_capabilities(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/BANK-02/capabilities"
    )

    assert response.status_code == 200

    assert response.json() == {
        "scenario_id": "BANK-02",
        "execution_modes": [
            "standard",
            "historical",
        ],
        "generation_lifecycles": [
            "bounded",
            "continuous",
        ],
        "historical": {
            "supported": True,
            "unavailable_reason": None,
            "configuration": {
                "degradation_samples": 4,
                "plateau_samples": 2,
                "recovery_samples": 4,
            },
        },
        "continuous": {
            "supported": True,
            "unavailable_reason": None,
            "configuration": {
                "stop_mode": "manual",
                "duration_seconds": None,
            },
        },
    }


def test_get_non_historical_scenario_capabilities(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/BANK-01/capabilities"
    )

    assert response.status_code == 200

    assert response.json() == {
        "scenario_id": "BANK-01",
        "execution_modes": [
            "standard",
        ],
        "generation_lifecycles": [
            "bounded",
            "continuous",
        ],
        "historical": {
            "supported": False,
            "unavailable_reason": (
                "Managed historical execution "
                "currently requires an incident "
                "and rollback scenario."
            ),
            "configuration": None,
        },
        "continuous": {
            "supported": True,
            "unavailable_reason": None,
            "configuration": {
                "stop_mode": "manual",
                "duration_seconds": None,
            },
        },
    }


def test_get_non_continuous_scenario_capabilities(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/INS-01/capabilities"
    )

    assert response.status_code == 200

    assert response.json() == {
        "scenario_id": "INS-01",
        "execution_modes": [
            "standard",
        ],
        "generation_lifecycles": [
            "bounded",
        ],
        "historical": {
            "supported": False,
            "unavailable_reason": (
                "Managed historical execution "
                "currently requires an incident "
                "and rollback scenario."
            ),
            "configuration": None,
        },
        "continuous": {
            "supported": False,
            "unavailable_reason": (
                "Scenario does not define "
                "continuous behaviour in its "
                "final active state."
            ),
            "configuration": None,
        },
    }


def test_insurance_rollback_supports_historical_execution(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/INS-02/capabilities"
    )

    assert response.status_code == 200

    assert (
        response.json()["execution_modes"]
        == [
            "standard",
            "historical",
        ]
    )

    historical = response.json()["historical"]

    assert historical["configuration"] == {
        "degradation_samples": 4,
        "plateau_samples": 2,
        "recovery_samples": 4,
    }


def test_unknown_scenario_capabilities_returns_404(
    client: TestClient,
) -> None:
    response = client.get(
        "/scenarios/UNKNOWN/capabilities"
    )

    assert response.status_code == 404


def test_start_historical_run_rejects_unsupported_scenario(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
            "execution_mode": "historical",
        },
    )

    assert response.status_code == 409

    assert response.json() == {
        "detail": (
            "Scenario 'BANK-01' does not "
            "support managed historical execution."
        )
    }


def test_start_historical_run_accepts_custom_configuration(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-02",
            "random_seed": 42,
            "execution_mode": "historical",
            "historical": {
                "degradation_samples": 6,
                "plateau_samples": 3,
                "recovery_samples": 5,
            },
        },
    )

    assert response.status_code == 202

    payload = response.json()

    assert payload[
        "historical_configuration"
    ] == {
        "degradation_samples": 6,
        "plateau_samples": 3,
        "recovery_samples": 5,
    }

    completed = wait_for_terminal_run(
        client,
        payload["run_id"],
    )

    assert completed["status"] == "completed"

    assert completed[
        "historical_configuration"
    ] == {
        "degradation_samples": 6,
        "plateau_samples": 3,
        "recovery_samples": 5,
    }

    assert completed["event_count"] == 60


def test_standard_run_rejects_historical_configuration(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "execution_mode": "standard",
            "historical": {
                "degradation_samples": 4,
                "plateau_samples": 2,
                "recovery_samples": 4,
            },
        },
    )

    assert response.status_code == 422


def test_historical_run_rejects_invalid_configuration(
    client: TestClient,
) -> None:
    response = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-02",
            "execution_mode": "historical",
            "historical": {
                "degradation_samples": 0,
                "plateau_samples": 2,
                "recovery_samples": 4,
            },
        },
    )

    assert response.status_code == 422


def test_get_run_events_returns_retained_events_in_sequence_order(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    response = client.get(
        f"/runs/{run_id}/events"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["run_id"] == run_id

    assert (
        payload["retained_event_count"]
        == completed["event_count"]
    )

    events = payload["events"]

    assert len(events) == (
        payload["retained_event_count"]
    )

    assert {
        event["run_id"]
        for event in events
    } == {run_id}

    assert [
        event["sequence_number"]
        for event in events
    ] == list(
        range(
            1,
            len(events) + 1,
        )
    )


def test_get_run_events_supports_sequence_cursor_pagination(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["event_count"] > 10

    first_response = client.get(
        f"/runs/{run_id}/events",
        params={
            "limit": 5,
        },
    )

    assert first_response.status_code == 200

    first_page = first_response.json()
    first_events = first_page["events"]

    assert (
        first_page["retained_event_count"]
        == completed["event_count"]
    )

    assert first_page[
        "returned_event_count"
    ] == 5

    assert [
        event["sequence_number"]
        for event in first_events
    ] == [1, 2, 3, 4, 5]

    assert first_page[
        "next_after_sequence_number"
    ] == 5

    second_response = client.get(
        f"/runs/{run_id}/events",
        params={
            "after_sequence_number": (
                first_page[
                    "next_after_sequence_number"
                ]
            ),
            "limit": 5,
        },
    )

    assert second_response.status_code == 200

    second_page = second_response.json()
    second_events = second_page["events"]

    assert (
        second_page["retained_event_count"]
        == completed["event_count"]
    )

    assert second_page[
        "returned_event_count"
    ] == 5

    assert [
        event["sequence_number"]
        for event in second_events
    ] == [6, 7, 8, 9, 10]

    assert second_page[
        "next_after_sequence_number"
    ] == 10


def test_get_run_events_last_page_has_no_next_cursor(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    total = completed["event_count"]

    assert total > 1

    response = client.get(
        f"/runs/{run_id}/events",
        params={
            "after_sequence_number": total - 2,
            "limit": 5,
        },
    )

    assert response.status_code == 200

    payload = response.json()
    events = payload["events"]

    assert payload["retained_event_count"] == total
    assert payload["returned_event_count"] == 2

    assert [
        event["sequence_number"]
        for event in events
    ] == [
        total - 1,
        total,
    ]

    assert (
        payload["next_after_sequence_number"]
        is None
    )


@pytest.mark.parametrize(
    ("params", "expected_status"),
    [
        ({"limit": 0}, 422),
        ({"limit": -1}, 422),
        (
            {"after_sequence_number": -1},
            422,
        ),
    ],
)
def test_get_run_events_rejects_invalid_pagination(
    client: TestClient,
    params: dict[str, int],
    expected_status: int,
) -> None:
    response = client.get(
        "/runs/RUN9999999/events",
        params=params,
    )

    assert response.status_code == expected_status


def test_get_run_events_filters_by_source_domain(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    response = client.get(
        f"/runs/{run_id}/events",
        params={
            "source_domain": "metric",
        },
    )

    assert response.status_code == 200

    payload = response.json()
    events = payload["events"]

    assert payload["run_id"] == run_id
    assert events

    assert {
        event["run_id"]
        for event in events
    } == {run_id}

    assert {
        event["source_domain"]
        for event in events
    } == {"metric"}

    assert (
        payload["retained_event_count"]
        == len(events)
    )

    assert (
        payload["retained_event_count"]
        < completed["event_count"]
    )

    assert [
        event["sequence_number"]
        for event in events
    ] == sorted(
        event["sequence_number"]
        for event in events
    )


def test_get_run_events_rejects_invalid_source_domain(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    response = client.get(
        f"/runs/{run_id}/events",
        params={
            "source_domain": "banana",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("parameter", "value"),
    [
        ("source_system", "missing_source"),
        ("event_type", "missing.event"),
        ("service", "missing_service"),
        ("component", "missing_component"),
    ],
)
def test_get_run_events_filters_by_string_projection(
    client: TestClient,
    parameter: str,
    value: str,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["event_count"] > 0

    response = client.get(
        f"/runs/{run_id}/events",
        params={
            parameter: value,
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["run_id"] == run_id
    assert payload["retained_event_count"] == 0
    assert payload["events"] == []


def test_get_run_events_combines_filters_with_and_semantics(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-01",
            "random_seed": 42,
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    wait_for_terminal_run(
        client,
        run_id,
    )

    metric_response = client.get(
        f"/runs/{run_id}/events",
        params={
            "source_domain": "metric",
        },
    )

    assert metric_response.status_code == 200
    assert (
        metric_response.json()["retained_event_count"]
        > 0
    )

    combined_response = client.get(
        f"/runs/{run_id}/events",
        params={
            "source_domain": "metric",
            "event_type": "missing.event",
        },
    )

    assert combined_response.status_code == 200

    payload = combined_response.json()

    assert payload["run_id"] == run_id
    assert payload["retained_event_count"] == 0
    assert payload["events"] == []


def test_get_custom_historical_run_events(
    client: TestClient,
) -> None:
    started = client.post(
        "/runs",
        json={
            "scenario_id": "BANK-02",
            "random_seed": 42,
            "execution_mode": "historical",
            "historical": {
                "degradation_samples": 6,
                "plateau_samples": 3,
                "recovery_samples": 5,
            },
        },
    )

    assert started.status_code == 202

    run_id = started.json()["run_id"]

    completed = wait_for_terminal_run(
        client,
        run_id,
    )

    assert completed["event_count"] == 60

    response = client.get(
        f"/runs/{run_id}/events"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["run_id"] == run_id
    assert payload["retained_event_count"] == 60

    assert [
        event["sequence_number"]
        for event in payload["events"]
    ] == list(
        range(1, 61)
    )


def test_get_run_events_returns_404_for_unknown_run(
    client: TestClient,
) -> None:
    response = client.get(
        "/runs/RUN9999999/events"
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": (
            "Run 'RUN9999999' was not found."
        )
    }