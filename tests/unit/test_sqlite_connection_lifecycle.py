import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import synthetic_ops_generator.control.sqlite_run_store as sqlite_run_store_module
import synthetic_ops_generator.core.sqlite_identifiers as sqlite_identifiers_module
import synthetic_ops_generator.retention.sqlite as sqlite_event_store_module
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)


def test_sqlite_id_factory_closes_connections_after_use(
    monkeypatch,
    tmp_path: Path,
) -> None:
    initialization_connection = MagicMock()
    initialization_connection.__enter__.return_value = (
        initialization_connection
    )

    runtime_connection = MagicMock()
    runtime_connection.__enter__.return_value = (
        runtime_connection
    )
    select_cursor = MagicMock()
    select_cursor.fetchone.return_value = None

    runtime_connection.execute.side_effect = [
        MagicMock(),
        select_cursor,
        MagicMock(),
    ]

    connections = iter(
        [
            initialization_connection,
            runtime_connection,
        ]
    )

    monkeypatch.setattr(
        sqlite_identifiers_module.sqlite3,
        "connect",
        lambda *args, **kwargs: next(connections),
    )

    ids = SQLiteIdFactory(
        database_path=(
            tmp_path
            / "identifiers.sqlite3"
        )
    )

    assert ids.run_id() == "RUN0000001"

    initialization_connection.close.assert_called_once_with()
    runtime_connection.close.assert_called_once_with()


class _TrackingConnection:
    def __init__(
        self,
        connection,
    ) -> None:
        self._connection = connection
        self.close_call_count = 0

    def __getattr__(
        self,
        name: str,
    ):
        return getattr(
            self._connection,
            name,
        )

    def __enter__(self):
        self._connection.__enter__()
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return self._connection.__exit__(
            exc_type,
            exc_value,
            traceback,
        )

    def close(self):
        self.close_call_count += 1
        return self._connection.close()


def _track_sqlite_connections(
    monkeypatch,
    sqlite_module,
):
    real_connect = (
        sqlite_module.sqlite3.connect
    )

    connections = []

    def tracked_connect(
        *args,
        **kwargs,
    ):
        connection = _TrackingConnection(
            real_connect(
                *args,
                **kwargs,
            )
        )

        connections.append(
            connection
        )

        return connection

    monkeypatch.setattr(
        sqlite_module.sqlite3,
        "connect",
        tracked_connect,
    )

    return connections


def test_sqlite_event_store_closes_connections_after_use(
    monkeypatch,
    tmp_path: Path,
) -> None:
    connections = _track_sqlite_connections(
        monkeypatch,
        sqlite_event_store_module,
    )

    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "events.sqlite3"
        )
    )

    asyncio.run(
        store.start()
    )

    events = asyncio.run(
        store.get_run_events(
            "RUN0000001"
        )
    )

    assert tuple(events) == ()

    asyncio.run(
        store.stop()
    )

    assert len(connections) == 2

    assert [
        connection.close_call_count
        for connection in connections
    ] == [
        1,
        1,
    ]


def test_sqlite_run_store_closes_connections_after_use(
    monkeypatch,
    tmp_path: Path,
) -> None:
    connections = _track_sqlite_connections(
        monkeypatch,
        sqlite_run_store_module,
    )

    store = SQLiteRunStore(
        database_path=(
            tmp_path
            / "runs.sqlite3"
        )
    )

    asyncio.run(
        store.start()
    )

    records = asyncio.run(
        store.list_all()
    )

    assert tuple(records) == ()

    asyncio.run(
        store.stop()
    )

    assert len(connections) == 2

    assert [
        connection.close_call_count
        for connection in connections
    ] == [
        1,
        1,
    ]
