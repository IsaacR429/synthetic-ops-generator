from pathlib import Path
from unittest.mock import MagicMock

import synthetic_ops_generator.core.sqlite_identifiers as sqlite_identifiers_module
from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
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
