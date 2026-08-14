from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from synthetic_ops_generator.control.models import (
    RunRecord,
    RunStatus,
)
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)


def make_run_record() -> RunRecord:
    return RunRecord(
        run_id="RUN0000001",
        scenario_id="BANK-01",
        change_id="CHG0000001",
        status=RunStatus.RUNNING,
        started_at=datetime(
            2026,
            8,
            14,
            0,
            0,
            tzinfo=UTC,
        ),
        completed_at=None,
        current_state=(
            OperationalState.INITIALISING
        ),
        event_count=0,
        validation_passed=None,
        random_seed=42,
        event_interval_seconds=5.0,
    )


@pytest.mark.asyncio
async def test_sqlite_run_store_round_trip(
    tmp_path: Path,
) -> None:
    store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()

    try:
        record = make_run_record()

        await store.create(record)

        stored = await store.get(
            record.run_id
        )

        assert stored == record

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_sqlite_run_store_updates_run(
    tmp_path: Path,
) -> None:
    store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()

    try:
        record = make_run_record()

        await store.create(record)

        completed = replace(
            record,
            status=RunStatus.COMPLETED,
            completed_at=datetime(
                2026,
                8,
                14,
                0,
                5,
                tzinfo=UTC,
            ),
            current_state=OperationalState.COMPLETED,
            event_count=32,
            validation_passed=True,
        )

        await store.update(completed)

        stored = await store.get(
            record.run_id
        )

        assert stored == completed

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_sqlite_run_store_survives_restart(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "runs.sqlite3"
    )

    first_store = SQLiteRunStore(
        database_path=database_path
    )

    await first_store.start()

    record = make_run_record()

    await first_store.create(record)
    await first_store.stop()

    second_store = SQLiteRunStore(
        database_path=database_path
    )

    await second_store.start()

    try:
        stored = await second_store.get(
            record.run_id
        )

        assert stored == record

    finally:
        await second_store.stop()


@pytest.mark.asyncio
async def test_sqlite_run_store_returns_none_for_unknown_run(
    tmp_path: Path,
) -> None:
    store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()

    try:
        stored = await store.get(
            "RUN9999999"
        )

        assert stored is None

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_sqlite_run_store_lists_runs_by_status(
    tmp_path: Path,
) -> None:
    store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()

    try:
        first_running = make_run_record()

        second_running = replace(
            first_running,
            run_id="RUN0000002",
            change_id="CHG0000002",
        )

        completed = replace(
            first_running,
            run_id="RUN0000003",
            change_id="CHG0000003",
            status=RunStatus.COMPLETED,
            completed_at=datetime(
                2026,
                8,
                14,
                0,
                5,
                tzinfo=UTC,
            ),
            current_state=(
                OperationalState.COMPLETED
            ),
            event_count=32,
            validation_passed=True,
        )

        await store.create(
            first_running
        )
        await store.create(
            second_running
        )
        await store.create(
            completed
        )

        running_records = (
            await store.list_by_status(
                RunStatus.RUNNING
            )
        )

        completed_records = (
            await store.list_by_status(
                RunStatus.COMPLETED
            )
        )

        assert [
            record.run_id
            for record in running_records
        ] == [
            "RUN0000001",
            "RUN0000002",
        ]

        assert completed_records == (
            completed,
        )

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_sqlite_run_store_returns_empty_status_list(
    tmp_path: Path,
) -> None:
    store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()

    try:
        records = (
            await store.list_by_status(
                RunStatus.FAILED
            )
        )

        assert records == ()

    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_sqlite_run_store_lists_running_runs_after_restart(
    tmp_path: Path,
) -> None:
    database_path = (
        tmp_path / "runs.sqlite3"
    )

    first_store = SQLiteRunStore(
        database_path=database_path
    )

    await first_store.start()

    record = make_run_record()

    await first_store.create(record)
    await first_store.stop()

    second_store = SQLiteRunStore(
        database_path=database_path
    )

    await second_store.start()

    try:
        running_records = (
            await second_store.list_by_status(
                RunStatus.RUNNING
            )
        )

        assert running_records == (
            record,
        )

    finally:
        await second_store.stop()
