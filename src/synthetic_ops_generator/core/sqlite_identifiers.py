import sqlite3
from pathlib import Path
from threading import Lock

from synthetic_ops_generator.core.identifiers import IdFactory


class SQLiteIdFactory(IdFactory):
    """
    Persistent identifier factory backed by SQLite.

    Identifier counters survive process restarts while preserving
    the existing identifier format used by IdFactory.
    """

    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        super().__init__()

        self._database_path = Path(database_path)
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._database_lock = Lock()

        self._initialize_database()

    def next(
        self,
        prefix: str,
        width: int = 7,
    ) -> str:
        if not prefix.strip():
            raise ValueError(
                "Identifier prefix is required."
            )

        if width <= 0:
            raise ValueError(
                "Identifier width must be greater than zero."
            )

        with self._database_lock:
            value = self._next_value(prefix)

        return f"{prefix}{value:0{width}d}"

    def _initialize_database(self) -> None:
        with sqlite3.connect(
            self._database_path,
            timeout=30.0,
        ) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS id_counters (
                    prefix TEXT PRIMARY KEY,
                    value INTEGER NOT NULL
                        CHECK(value >= 0)
                )
                """
            )

    def _next_value(
        self,
        prefix: str,
    ) -> int:
        with sqlite3.connect(
            self._database_path,
            timeout=30.0,
        ) as connection:
            connection.execute(
                "BEGIN IMMEDIATE"
            )

            row = connection.execute(
                """
                SELECT value
                FROM id_counters
                WHERE prefix = ?
                """,
                (prefix,),
            ).fetchone()

            if row is None:
                value = 1

                connection.execute(
                    """
                    INSERT INTO id_counters (
                        prefix,
                        value
                    )
                    VALUES (?, ?)
                    """,
                    (
                        prefix,
                        value,
                    ),
                )
            else:
                value = int(row[0]) + 1

                connection.execute(
                    """
                    UPDATE id_counters
                    SET value = ?
                    WHERE prefix = ?
                    """,
                    (
                        value,
                        prefix,
                    ),
                )

        return value