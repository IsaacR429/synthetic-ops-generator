import asyncio
import sqlite3
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from synthetic_ops_generator.api.app import create_app
from synthetic_ops_generator.control.configuration import (
    HistoricalExecutionConfiguration,
)
from synthetic_ops_generator.control.models import (
    RunExecutionMode,
    RunRecord,
    RunStatus,
)
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.publishers.base import (
    EventPublisher,
)


class BlockingPublisher(EventPublisher):
    """
    Holds Scenario execution at its first publish
    until the task is cancelled.
    """

    def __init__(self) -> None:
        self.blocked = threading.Event()

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        self.blocked.set()

        await asyncio.sleep(3600)


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


def test_run_ids_survive_application_restart(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    first_app = create_app(
        data_root=data_root
    )

    with TestClient(first_app) as client:
        first = client.post(
            "/runs",
            json={
                "scenario_id": "BANK-01",
                "random_seed": 42,
            },
        )

        assert first.status_code == 202
        assert first.json() == {
            "scenario_id": "BANK-01",
            "run_id": "RUN0000001",
            "change_id": "CHG0000001",
            "status": "running",
            "execution_mode": "standard",
            "generation_lifecycle": "bounded",
            "historical_configuration": None,
            "continuous_configuration": None,
        }

        first_completed = (
            wait_for_terminal_run(
                client,
                "RUN0000001",
            )
        )

        assert (
            first_completed["status"]
            == "completed"
        )
        assert (
            first_completed["event_count"]
            == 32
        )
        assert (
            first_completed[
                "validation_passed"
            ]
            is True
        )

    second_app = create_app(
        data_root=data_root
    )

    with TestClient(second_app) as client:
        first_record = client.get(
            "/runs/RUN0000001"
        )

        assert first_record.status_code == 200

        first_payload = (
            first_record.json()
        )

        assert (
            first_payload["status"]
            == "completed"
        )
        assert (
            first_payload["event_count"]
            == 32
        )
        assert (
            first_payload[
                "validation_passed"
            ]
            is True
        )

        replayed = client.post(
            "/runs/RUN0000001/replay"
        )

        assert replayed.status_code == 200
        assert replayed.json() == {
            "run_id": "RUN0000001",
            "scenario_id": "BANK-01",
            "replayed_event_count": 32,
        }

        second = client.post(
            "/runs",
            json={
                "scenario_id": "INS-01",
                "random_seed": 42,
            },
        )

        assert second.status_code == 202
        assert (
            second.json()["run_id"]
            == "RUN0000002"
        )
        assert (
            second.json()["change_id"]
            == "CHG0000002"
        )
        assert (
            second.json()["status"]
            == "running"
        )

        second_completed = (
            wait_for_terminal_run(
                client,
                "RUN0000002",
            )
        )

        assert (
            second_completed["status"]
            == "completed"
        )
        assert (
            second_completed["event_count"]
            == 32
        )


async def seed_orphaned_run(
    database_path: Path,
) -> None:
    store = SQLiteRunStore(
        database_path=database_path
    )

    await store.start()

    try:
        await store.create(
            RunRecord(
                run_id="RUN0000042",
                scenario_id="BANK-01",
                change_id="CHG0000042",
                status=RunStatus.RUNNING,
                started_at=datetime.now(UTC),
                completed_at=None,
                current_state=(
                    OperationalState.IMPLEMENTING
                ),
                event_count=0,
                validation_passed=None,
                random_seed=42,
                event_interval_seconds=5.0,
            )
        )
    finally:
        await store.stop()


def test_application_startup_reconciles_orphaned_run(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    asyncio.run(
        seed_orphaned_run(
            data_root / "runs.sqlite3"
        )
    )

    app = create_app(
        data_root=data_root
    )

    with TestClient(app) as client:
        response = client.get(
            "/runs/RUN0000042"
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["status"] == "failed"
        assert (
            payload["current_state"]
            == "implementing"
        )
        assert payload["event_count"] == 0
        assert (
            payload["validation_passed"]
            is None
        )
        assert (
            payload["completed_at"]
            is not None
        )
        assert payload["error_message"] == (
            "Run interrupted by "
            "application restart."
        )


def test_graceful_shutdown_stops_active_run_and_preserves_status_after_restart(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    blocking_publisher = (
        BlockingPublisher()
    )

    first_app = create_app(
        data_root=data_root,
        execution_publisher_factory=(
            lambda: blocking_publisher
        ),
    )

    with TestClient(first_app) as client:
        started = client.post(
            "/runs",
            json={
                "scenario_id": "BANK-01",
                "random_seed": 42,
            },
        )

        assert started.status_code == 202

        run_id = started.json()["run_id"]

        assert (
            started.json()["status"]
            == "running"
        )

        assert blocking_publisher.blocked.wait(
            timeout=5.0
        )

        live = client.get(
            f"/runs/{run_id}"
        )

        assert live.status_code == 200
        assert (
            live.json()["status"]
            == "running"
        )

    # Leaving TestClient invokes the FastAPI lifespan:
    #
    # ActiveRunManager.shutdown()
    #     -> task.cancel()
    #     -> ControlService catches CancelledError
    #     -> RunStore persists STOPPED
    #     -> RunStore then closes.

    second_app = create_app(
        data_root=data_root
    )

    with TestClient(second_app) as client:
        persisted = client.get(
            f"/runs/{run_id}"
        )

        assert persisted.status_code == 200

        payload = persisted.json()

        assert payload["status"] == "stopped"

        assert (
            payload["completed_at"]
            is not None
        )

        assert (
            payload["validation_passed"]
            is None
        )

        assert payload["error_message"] is None

        assert payload["execution_mode"] == "standard"

        assert payload["event_count"] == 0


def test_graceful_shutdown_stops_historical_run_and_preserves_status_after_restart(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    blocking_publisher = (
        BlockingPublisher()
    )

    first_app = create_app(
        data_root=data_root,
        execution_publisher_factory=(
            lambda: blocking_publisher
        ),
    )

    with TestClient(first_app) as client:
        started = client.post(
            "/runs",
            json={
                "scenario_id": "BANK-02",
                "random_seed": 42,
                "execution_mode": (
                    "historical"
                ),
            },
        )

        assert started.status_code == 202

        started_payload = started.json()

        assert (
            started_payload["status"]
            == "running"
        )

        assert (
            started_payload[
                "execution_mode"
            ]
            == "historical"
        )

        run_id = started_payload["run_id"]

        assert blocking_publisher.blocked.wait(
            timeout=5.0
        )

        live = client.get(
            f"/runs/{run_id}"
        )

        assert live.status_code == 200

        live_payload = live.json()

        assert (
            live_payload["status"]
            == "running"
        )

        assert (
            live_payload[
                "execution_mode"
            ]
            == "historical"
        )

    # Leaving TestClient invokes the FastAPI
    # lifespan:
    #
    # ActiveRunManager.shutdown()
    #     -> task.cancel()
    #     -> ControlService catches CancelledError
    #     -> latest historical progress is read
    #     -> RunStore persists STOPPED
    #     -> RunStore then closes.

    second_app = create_app(
        data_root=data_root
    )

    with TestClient(second_app) as client:
        persisted = client.get(
            f"/runs/{run_id}"
        )

        assert persisted.status_code == 200

        payload = persisted.json()

        assert (
            payload["status"]
            == "stopped"
        )

        assert (
            payload["execution_mode"]
            == "historical"
        )

        assert payload["event_count"] == 0

        assert (
            payload["validation_passed"]
            is None
        )

        assert (
            payload["completed_at"]
            is not None
        )

        assert payload["error_message"] is None


def test_historical_run_survives_application_restart(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    first_app = create_app(
        data_root=data_root
    )

    with TestClient(first_app) as client:
        started = client.post(
            "/runs",
            json={
                "scenario_id": "BANK-02",
                "random_seed": 42,
                "execution_mode": (
                    "historical"
                ),
            },
        )

        assert started.status_code == 202

        payload = started.json()

        assert (
            payload["execution_mode"]
            == "historical"
        )

        run_id = payload["run_id"]

        completed = wait_for_terminal_run(
            client,
            run_id,
        )

        assert (
            completed["status"]
            == "completed"
        )

        assert (
            completed["execution_mode"]
            == "historical"
        )

        assert (
            completed["event_count"]
            == 48
        )

        assert (
            completed["validation_passed"]
            is None
        )

    second_app = create_app(
        data_root=data_root
    )

    with TestClient(second_app) as client:
        restored = client.get(
            f"/runs/{run_id}"
        )

        assert restored.status_code == 200

        restored_payload = (
            restored.json()
        )

        assert (
            restored_payload["status"]
            == "completed"
        )

        assert (
            restored_payload[
                "execution_mode"
            ]
            == "historical"
        )

        assert (
            restored_payload["event_count"]
            == 48
        )

        assert (
            restored_payload[
                "validation_passed"
            ]
            is None
        )

        replayed = client.post(
            f"/runs/{run_id}/replay"
        )

        assert replayed.status_code == 200

        assert replayed.json() == {
            "run_id": run_id,
            "scenario_id": "BANK-02",
            "replayed_event_count": 48,
        }


def test_custom_historical_configuration_survives_application_restart(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    first_app = create_app(
        data_root=data_root
    )

    with TestClient(first_app) as client:
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

    second_app = create_app(
        data_root=data_root
    )

    with TestClient(second_app) as client:
        restored = client.get(
            f"/runs/{run_id}"
        )

        assert restored.status_code == 200

        payload = restored.json()

        assert (
            payload["historical_configuration"]
            == {
                "degradation_samples": 6,
                "plateau_samples": 3,
                "recovery_samples": 5,
            }
        )

        assert payload["event_count"] == 60


def test_legacy_historical_run_migration_backfills_default_configuration(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "runs" / "runs.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE runs (
                run_id TEXT PRIMARY KEY,
                scenario_id TEXT NOT NULL,
                change_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                current_state TEXT NOT NULL,
                event_count INTEGER NOT NULL CHECK(event_count >= 0),
                validation_passed INTEGER,
                random_seed INTEGER NOT NULL,
                event_interval_seconds REAL NOT NULL CHECK(event_interval_seconds > 0),
                error_message TEXT,
                execution_mode TEXT NOT NULL DEFAULT 'standard'
            )
            """
        )
        conn.execute(
            """
            INSERT INTO runs (
                run_id, scenario_id, change_id, status, started_at,
                completed_at, current_state, event_count, validation_passed,
                random_seed, event_interval_seconds, error_message, execution_mode
            ) VALUES (
                'RUN0000001', 'BANK-02', 'CHG0000001', 'completed',
                '2026-08-01T10:00:00+00:00', '2026-08-01T10:01:00+00:00',
                'completed', 48, NULL, 42, 5.0, NULL, 'historical'
            )
            """
        )

    store = SQLiteRunStore(database_path=db_path)
    asyncio.run(store.start())

    record = asyncio.run(store.get("RUN0000001"))
    assert record is not None
    assert record.execution_mode == RunExecutionMode.HISTORICAL
    assert record.historical_configuration == HistoricalExecutionConfiguration(
        degradation_samples=4,
        plateau_samples=2,
        recovery_samples=4,
    )