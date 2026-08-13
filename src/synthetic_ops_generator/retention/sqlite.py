import asyncio
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    deserialize_generated_event,
    serialize_generated_event,
)
from synthetic_ops_generator.retention.base import EventStore


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
                    UNIQUE(run_id, sequence_number)
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_generated_events_run_sequence
                ON generated_events (
                    run_id,
                    sequence_number
                )
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
                    payload
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.run_id,
                    event.sequence_number,
                    event.event_time.astimezone(
                        UTC
                    ).isoformat(),
                    payload,
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
