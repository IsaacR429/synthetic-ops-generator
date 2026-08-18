import asyncio
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    deserialize_generated_event,
    serialize_generated_event,
)
from synthetic_ops_generator.retention.base import EventStore
from synthetic_ops_generator.retention.query import EventQuery


class SQLiteEventStore(EventStore):
    """
    SQLite-backed persistent store for canonical GeneratedEvents.

    Canonical event payloads are stored as serialized JSON bytes.
    Run ID and sequence number are indexed for deterministic replay.
    """

    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(database_path)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        await asyncio.to_thread(
            self._initialize_database
        )

        self._started = True

    async def append(
        self,
        event: GeneratedEvent,
    ) -> None:
        self._require_started()

        await asyncio.to_thread(
            self._append_sync,
            event,
        )

    async def get_run_events(
        self,
        run_id: str,
    ) -> Sequence[GeneratedEvent]:
        self._require_started()

        if not run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        return await asyncio.to_thread(
            self._get_run_events_sync,
            run_id,
        )

    async def query_events(
        self,
        query: EventQuery,
    ) -> Sequence[GeneratedEvent]:
        self._require_started()

        if not query.run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        if query.limit is not None and query.limit <= 0:
            raise ValueError(
                "Event query limit must be greater than zero."
            )

        if (
            query.after_sequence_number is not None
            and query.after_sequence_number < 0
        ):
            raise ValueError(
                "Event query sequence cursor cannot be negative."
            )

        return await asyncio.to_thread(
            self._query_events_sync,
            query,
        )

    async def count_events(
        self,
        query: EventQuery,
    ) -> int:
        self._require_started()

        if not query.run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        return await asyncio.to_thread(
            self._count_events_sync,
            query,
        )

    async def delete_before(
        self,
        cutoff: datetime,
    ) -> int:
        self._require_started()

        if (
            cutoff.tzinfo is None
            or cutoff.utcoffset() is None
        ):
            raise ValueError(
                "Retention cutoff must be timezone-aware."
            )

        cutoff_utc = cutoff.astimezone(
            UTC
        ).isoformat()

        return await asyncio.to_thread(
            self._delete_before_sync,
            cutoff_utc,
        )

    async def stop(self) -> None:
        self._started = False

    def _initialize_database(self) -> None:
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with sqlite3.connect(
            self._database_path
        ) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS generated_events (
                    event_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    event_time TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    source_domain TEXT,
                    source_system TEXT,
                    event_type TEXT,
                    service TEXT,
                    component TEXT,
                    UNIQUE(run_id, sequence_number)
                )
                """
            )

            projection_columns_added = (
                self._ensure_projection_columns(
                    connection
                )
            )

            if projection_columns_added:
                self._backfill_projection_columns(
                    connection
                )

            connection.execute(
                """
                DROP INDEX IF EXISTS
                idx_generated_events_run_sequence
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_generated_events_event_time
                ON generated_events (
                    event_time
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_generated_events_run_domain_sequence
                ON generated_events (
                    run_id,
                    source_domain,
                    sequence_number
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_generated_events_run_type_sequence
                ON generated_events (
                    run_id,
                    event_type,
                    sequence_number
                )
                """
            )

    @staticmethod
    def _ensure_projection_columns(
        connection: sqlite3.Connection,
    ) -> bool:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(generated_events)"
            ).fetchall()
        }

        projection_cols = [
            ("source_domain", "TEXT"),
            ("source_system", "TEXT"),
            ("event_type", "TEXT"),
            ("service", "TEXT"),
            ("component", "TEXT"),
        ]

        columns_added = False

        for col_name, col_type in projection_cols:
            if col_name not in columns:
                connection.execute(
                    f"ALTER TABLE generated_events "
                    f"ADD COLUMN {col_name} {col_type}"
                )
                columns_added = True

        return columns_added

    @staticmethod
    def _backfill_projection_columns(
        connection: sqlite3.Connection,
    ) -> None:
        rows = connection.execute(
            """
            SELECT
                event_id,
                payload
            FROM generated_events
            """
        ).fetchall()

        updates = []

        for event_id, payload in rows:
            event = deserialize_generated_event(
                payload
            )

            updates.append(
                (
                    event.source_system,
                    event.event_type,
                    event.service,
                    event.component,
                    event_id,
                )
            )

        connection.executemany(
            """
            UPDATE generated_events
            SET
                source_system = COALESCE(
                    source_system,
                    ?
                ),
                event_type = COALESCE(
                    event_type,
                    ?
                ),
                service = COALESCE(
                    service,
                    ?
                ),
                component = COALESCE(
                    component,
                    ?
                )
            WHERE event_id = ?
            """,
            updates,
        )

    def _append_sync(
        self,
        event: GeneratedEvent,
    ) -> None:
        payload = serialize_generated_event(
            event
        )

        with sqlite3.connect(
            self._database_path
        ) as connection:
            connection.execute(
                """
                INSERT INTO generated_events (
                    event_id,
                    run_id,
                    sequence_number,
                    event_time,
                    payload,
                    source_domain,
                    source_system,
                    event_type,
                    service,
                    component
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.run_id,
                    event.sequence_number,
                    event.event_time.astimezone(
                        UTC
                    ).isoformat(),
                    payload,
                    (
                        event.source_domain.value
                        if event.source_domain is not None
                        else None
                    ),
                    event.source_system,
                    event.event_type,
                    event.service,
                    event.component,
                ),
            )

    def _get_run_events_sync(
        self,
        run_id: str,
    ) -> tuple[GeneratedEvent, ...]:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            rows = connection.execute(
                """
                SELECT payload
                FROM generated_events
                WHERE run_id = ?
                ORDER BY sequence_number ASC
                """,
                (run_id,),
            ).fetchall()

        return tuple(
            deserialize_generated_event(
                row[0]
            )
            for row in rows
        )

    def _query_events_sync(
        self,
        query: EventQuery,
    ) -> tuple[GeneratedEvent, ...]:
        where_clauses = ["run_id = ?"]
        params: list[Any] = [query.run_id]

        if query.source_domain is not None:
            where_clauses.append("source_domain = ?")
            params.append(
                query.source_domain.value
            )

        if query.source_system is not None:
            where_clauses.append("source_system = ?")
            params.append(query.source_system)

        if query.event_type is not None:
            where_clauses.append("event_type = ?")
            params.append(query.event_type)

        if query.service is not None:
            where_clauses.append("service = ?")
            params.append(query.service)

        if query.component is not None:
            where_clauses.append("component = ?")
            params.append(query.component)

        if query.after_sequence_number is not None:
            where_clauses.append("sequence_number > ?")
            params.append(query.after_sequence_number)

        sql = f"""
        SELECT payload
        FROM generated_events
        WHERE {" AND ".join(where_clauses)}
        ORDER BY sequence_number ASC
        """

        if query.limit is not None:
            sql += "\nLIMIT ?"
            params.append(query.limit)

        with sqlite3.connect(
            self._database_path
        ) as connection:
            rows = connection.execute(
                sql,
                params,
            ).fetchall()

        return tuple(
            deserialize_generated_event(
                row[0]
            )
            for row in rows
        )

    def _count_events_sync(
        self,
        query: EventQuery,
    ) -> int:
        where_clauses = ["run_id = ?"]
        params: list[Any] = [query.run_id]

        if query.source_domain is not None:
            where_clauses.append("source_domain = ?")
            params.append(
                query.source_domain.value
            )

        if query.source_system is not None:
            where_clauses.append("source_system = ?")
            params.append(query.source_system)

        if query.event_type is not None:
            where_clauses.append("event_type = ?")
            params.append(query.event_type)

        if query.service is not None:
            where_clauses.append("service = ?")
            params.append(query.service)

        if query.component is not None:
            where_clauses.append("component = ?")
            params.append(query.component)

        sql = f"""
        SELECT COUNT(*)
        FROM generated_events
        WHERE {" AND ".join(where_clauses)}
        """

        with sqlite3.connect(
            self._database_path
        ) as connection:
            row = connection.execute(
                sql,
                params,
            ).fetchone()

        if row is None:
            return 0

        return int(row[0])

    def _delete_before_sync(
        self,
        cutoff_utc: str,
    ) -> int:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            cursor = connection.execute(
                """
                DELETE FROM generated_events
                WHERE event_time < ?
                """,
                (cutoff_utc,),
            )

            deleted_count = cursor.rowcount

        return deleted_count

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError(
                "SQLiteEventStore is not started."
            )
