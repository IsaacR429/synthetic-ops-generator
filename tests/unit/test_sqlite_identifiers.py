from pathlib import Path

from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
)


def test_sqlite_id_factory_preserves_identifier_format(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "identifiers.sqlite3"

    ids = SQLiteIdFactory(
        database_path=database_path
    )

    assert ids.run_id() == "RUN0000001"
    assert ids.change_id() == "CHG0000001"
    assert ids.event_id() == "EVT0000001"


def test_sqlite_id_factory_persists_counters_across_instances(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "identifiers.sqlite3"

    first_factory = SQLiteIdFactory(
        database_path=database_path
    )

    assert first_factory.run_id() == "RUN0000001"
    assert first_factory.run_id() == "RUN0000002"

    second_factory = SQLiteIdFactory(
        database_path=database_path
    )

    assert second_factory.run_id() == "RUN0000003"


def test_sqlite_id_factory_keeps_prefix_counters_independent(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "identifiers.sqlite3"

    ids = SQLiteIdFactory(
        database_path=database_path
    )

    assert ids.run_id() == "RUN0000001"
    assert ids.change_id() == "CHG0000001"
    assert ids.event_id() == "EVT0000001"

    assert ids.run_id() == "RUN0000002"
    assert ids.change_id() == "CHG0000002"
    assert ids.event_id() == "EVT0000002"