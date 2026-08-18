import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.control.configuration import (
    ContinuousExecutionConfiguration,
    ContinuousStopMode,
    GenerationLifecycle,
    HistoricalExecutionConfiguration,
)
from synthetic_ops_generator.control.models import (
    RunExecutionMode,
    RunRecord,
    RunStatus,
    RunTargetSnapshot,
)
from synthetic_ops_generator.control.run_store import (
    RunStore,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
)


class SQLiteRunStore(RunStore):
    """
    SQLite-backed persistent store for Scenario Run metadata.
    """

    def __init__(
        self,
        *,
        database_path: str | Path,
    ) -> None:
        self._database_path = Path(
            database_path
        )
        self._started = False

    async def start(self) -> None:
        if self._started:
            return

        await asyncio.to_thread(
            self._initialize_database
        )

        self._started = True

    async def create(
        self,
        record: RunRecord,
    ) -> None:
        self._require_started()
        self._validate_record(record)

        try:
            await asyncio.to_thread(
                self._create_sync,
                record,
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Run already exists: {record.run_id}"
            ) from exc

    async def get(
        self,
        run_id: str,
    ) -> RunRecord | None:
        self._require_started()

        if not run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        return await asyncio.to_thread(
            self._get_sync,
            run_id,
        )

    async def list_all(
        self,
    ) -> tuple[RunRecord, ...]:
        self._require_started()

        return await asyncio.to_thread(
            self._list_all_sync,
        )

    async def list_by_status(
        self,
        status: RunStatus,
    ) -> tuple[RunRecord, ...]:
        self._require_started()

        return await asyncio.to_thread(
            self._list_by_status_sync,
            status,
        )

    async def update(
        self,
        record: RunRecord,
    ) -> None:
        self._require_started()
        self._validate_record(record)

        updated = await asyncio.to_thread(
            self._update_sync,
            record,
        )

        if not updated:
            raise ValueError(
                f"Run does not exist: {record.run_id}"
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
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    change_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    current_state TEXT NOT NULL,
                    event_count INTEGER NOT NULL
                        CHECK(event_count >= 0),
                    validation_passed INTEGER,
                    random_seed INTEGER NOT NULL,
                    event_interval_seconds REAL NOT NULL
                        CHECK(event_interval_seconds > 0),
                    error_message TEXT,
                    execution_mode TEXT NOT NULL
                        DEFAULT 'standard',
                    historical_degradation_samples INTEGER
                        CHECK(
                            historical_degradation_samples IS NULL
                            OR historical_degradation_samples > 0
                        ),
                    historical_plateau_samples INTEGER
                        CHECK(
                            historical_plateau_samples IS NULL
                            OR historical_plateau_samples >= 0
                        ),
                    historical_recovery_samples INTEGER
                        CHECK(
                            historical_recovery_samples IS NULL
                            OR historical_recovery_samples >= 0
                        ),
                    generation_lifecycle TEXT NOT NULL
                        DEFAULT 'bounded',
                    continuous_stop_mode TEXT,
                    continuous_duration_seconds INTEGER
                        CHECK(
                            continuous_duration_seconds IS NULL
                            OR continuous_duration_seconds > 0
                        ),
                    enterprise_id TEXT,
                    business_stream_id TEXT,
                    service_id TEXT,
                    target_component_ids TEXT,
                    target_environment TEXT
                )
                """
            )

            self._ensure_execution_mode_column(
                connection
            )

            self._ensure_historical_configuration_columns(
                connection
            )

            self._ensure_generation_lifecycle_columns(
                connection
            )

            self._ensure_target_snapshot_columns(
                connection
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_runs_scenario_id
                ON runs (scenario_id)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_runs_status
                ON runs (status)
                """
            )

    @staticmethod
    def _ensure_execution_mode_column(
        connection: sqlite3.Connection,
    ) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(runs)"
            ).fetchall()
        }

        if "execution_mode" in columns:
            return

        connection.execute(
            """
            ALTER TABLE runs
            ADD COLUMN execution_mode TEXT NOT NULL
            DEFAULT 'standard'
            """
        )

    @staticmethod
    def _ensure_historical_configuration_columns(
        connection: sqlite3.Connection,
    ) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(runs)"
            ).fetchall()
        }

        if (
            "historical_degradation_samples"
            not in columns
        ):
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN
                historical_degradation_samples
                INTEGER
                CHECK(
                    historical_degradation_samples
                    IS NULL
                    OR
                    historical_degradation_samples > 0
                )
                """
            )

        if (
            "historical_plateau_samples"
            not in columns
        ):
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN
                historical_plateau_samples
                INTEGER
                CHECK(
                    historical_plateau_samples
                    IS NULL
                    OR historical_plateau_samples >= 0
                )
                """
            )

        if (
            "historical_recovery_samples"
            not in columns
        ):
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN
                historical_recovery_samples
                INTEGER
                CHECK(
                    historical_recovery_samples
                    IS NULL
                    OR historical_recovery_samples >= 0
                )
                """
            )

        connection.execute(
            """
            UPDATE runs
            SET
                historical_degradation_samples =
                    COALESCE(
                        historical_degradation_samples,
                        4
                    ),
                historical_plateau_samples =
                    COALESCE(
                        historical_plateau_samples,
                        2
                    ),
                historical_recovery_samples =
                    COALESCE(
                        historical_recovery_samples,
                        4
                    )
            WHERE execution_mode = 'historical'
            """
        )

    @staticmethod
    def _ensure_generation_lifecycle_columns(
        connection: sqlite3.Connection,
    ) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(runs)"
            ).fetchall()
        }

        if "generation_lifecycle" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN generation_lifecycle TEXT NOT NULL
                DEFAULT 'bounded'
                """
            )

        if "continuous_stop_mode" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN continuous_stop_mode TEXT
                """
            )

        if "continuous_duration_seconds" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN continuous_duration_seconds INTEGER
                CHECK(
                    continuous_duration_seconds IS NULL
                    OR continuous_duration_seconds > 0
                )
                """
            )

    @staticmethod
    def _ensure_target_snapshot_columns(
        connection: sqlite3.Connection,
    ) -> None:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(runs)"
            ).fetchall()
        }

        if "enterprise_id" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN enterprise_id TEXT
                """
            )

        if "business_stream_id" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN business_stream_id TEXT
                """
            )

        if "service_id" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN service_id TEXT
                """
            )

        if "target_component_ids" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN target_component_ids TEXT
                """
            )

        if "target_environment" not in columns:
            connection.execute(
                """
                ALTER TABLE runs
                ADD COLUMN target_environment TEXT
                """
            )

    def _create_sync(
        self,
        record: RunRecord,
    ) -> None:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id,
                    scenario_id,
                    change_id,
                    status,
                    started_at,
                    completed_at,
                    current_state,
                    event_count,
                    validation_passed,
                    random_seed,
                    event_interval_seconds,
                    error_message,
                    execution_mode,
                    historical_degradation_samples,
                    historical_plateau_samples,
                    historical_recovery_samples,
                    generation_lifecycle,
                    continuous_stop_mode,
                    continuous_duration_seconds,
                    enterprise_id,
                    business_stream_id,
                    service_id,
                    target_component_ids,
                    target_environment
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                self._record_values(record),
            )

    def _get_sync(
        self,
        run_id: str,
    ) -> RunRecord | None:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            row = connection.execute(
                """
                SELECT
                    run_id,
                    scenario_id,
                    change_id,
                    status,
                    started_at,
                    completed_at,
                    current_state,
                    event_count,
                    validation_passed,
                    random_seed,
                    event_interval_seconds,
                    error_message,
                    execution_mode,
                    historical_degradation_samples,
                    historical_plateau_samples,
                    historical_recovery_samples,
                    generation_lifecycle,
                    continuous_stop_mode,
                    continuous_duration_seconds,
                    enterprise_id,
                    business_stream_id,
                    service_id,
                    target_component_ids,
                    target_environment
                FROM runs
                WHERE run_id = ?
                """,
                (run_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_record(row)

    def _list_all_sync(
        self,
    ) -> tuple[RunRecord, ...]:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            rows = connection.execute(
                """
                SELECT
                    run_id,
                    scenario_id,
                    change_id,
                    status,
                    started_at,
                    completed_at,
                    current_state,
                    event_count,
                    validation_passed,
                    random_seed,
                    event_interval_seconds,
                    error_message,
                    execution_mode,
                    historical_degradation_samples,
                    historical_plateau_samples,
                    historical_recovery_samples,
                    generation_lifecycle,
                    continuous_stop_mode,
                    continuous_duration_seconds,
                    enterprise_id,
                    business_stream_id,
                    service_id,
                    target_component_ids,
                    target_environment
                FROM runs
                ORDER BY started_at DESC, run_id DESC
                """
            ).fetchall()

        return tuple(
            self._row_to_record(row)
            for row in rows
        )

    def _list_by_status_sync(
        self,
        status: RunStatus,
    ) -> tuple[RunRecord, ...]:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            rows = connection.execute(
                """
                SELECT
                    run_id,
                    scenario_id,
                    change_id,
                    status,
                    started_at,
                    completed_at,
                    current_state,
                    event_count,
                    validation_passed,
                    random_seed,
                    event_interval_seconds,
                    error_message,
                    execution_mode,
                    historical_degradation_samples,
                    historical_plateau_samples,
                    historical_recovery_samples,
                    generation_lifecycle,
                    continuous_stop_mode,
                    continuous_duration_seconds,
                    enterprise_id,
                    business_stream_id,
                    service_id,
                    target_component_ids,
                    target_environment
                FROM runs
                WHERE status = ?
                ORDER BY started_at, run_id
                """,
                (status.value,),
            ).fetchall()

        return tuple(
            self._row_to_record(row)
            for row in rows
        )

    def _update_sync(
        self,
        record: RunRecord,
    ) -> bool:
        with sqlite3.connect(
            self._database_path
        ) as connection:
            cursor = connection.execute(
                """
                UPDATE runs
                SET
                    scenario_id = ?,
                    change_id = ?,
                    status = ?,
                    started_at = ?,
                    completed_at = ?,
                    current_state = ?,
                    event_count = ?,
                    validation_passed = ?,
                    random_seed = ?,
                    event_interval_seconds = ?,
                    error_message = ?,
                    execution_mode = ?,
                    historical_degradation_samples = ?,
                    historical_plateau_samples = ?,
                    historical_recovery_samples = ?,
                    generation_lifecycle = ?,
                    continuous_stop_mode = ?,
                    continuous_duration_seconds = ?
                WHERE run_id = ?
                """,
                (
                    record.scenario_id,
                    record.change_id,
                    record.status.value,
                    self._datetime_to_text(
                        record.started_at
                    ),
                    (
                        self._datetime_to_text(
                            record.completed_at
                        )
                        if record.completed_at
                        is not None
                        else None
                    ),
                    record.current_state.value,
                    record.event_count,
                    (
                        int(record.validation_passed)
                        if record.validation_passed
                        is not None
                        else None
                    ),
                    record.random_seed,
                    record.event_interval_seconds,
                    record.error_message,
                    record.execution_mode.value,
                    (
                        record.historical_configuration
                        .degradation_samples
                        if record.historical_configuration
                        is not None
                        else None
                    ),
                    (
                        record.historical_configuration
                        .plateau_samples
                        if record.historical_configuration
                        is not None
                        else None
                    ),
                    (
                        record.historical_configuration
                        .recovery_samples
                        if record.historical_configuration
                        is not None
                        else None
                    ),
                    record.generation_lifecycle.value,
                    (
                        record.continuous_configuration
                        .stop_mode.value
                        if record.continuous_configuration
                        is not None
                        else None
                    ),
                    (
                        record.continuous_configuration
                        .duration_seconds
                        if record.continuous_configuration
                        is not None
                        else None
                    ),
                    record.run_id,
                ),
            )

            return cursor.rowcount > 0

    def _record_values(
        self,
        record: RunRecord,
    ) -> tuple[object, ...]:
        return (
            record.run_id,
            record.scenario_id,
            record.change_id,
            record.status.value,
            self._datetime_to_text(
                record.started_at
            ),
            (
                self._datetime_to_text(
                    record.completed_at
                )
                if record.completed_at is not None
                else None
            ),
            record.current_state.value,
            record.event_count,
            (
                int(record.validation_passed)
                if record.validation_passed
                is not None
                else None
            ),
            record.random_seed,
            record.event_interval_seconds,
            record.error_message,
            record.execution_mode.value,
            (
                record.historical_configuration
                .degradation_samples
                if record.historical_configuration
                is not None
                else None
            ),
            (
                record.historical_configuration
                .plateau_samples
                if record.historical_configuration
                is not None
                else None
            ),
            (
                record.historical_configuration
                .recovery_samples
                if record.historical_configuration
                is not None
                else None
            ),
            record.generation_lifecycle.value,
            (
                record.continuous_configuration
                .stop_mode.value
                if record.continuous_configuration
                is not None
                else None
            ),
            (
                record.continuous_configuration
                .duration_seconds
                if record.continuous_configuration
                is not None
                else None
            ),
            *SQLiteRunStore._target_values(record),
        )

    @staticmethod
    def _target_values(
        record: RunRecord,
    ) -> tuple[object, ...]:
        if record.target is None:
            return (
                None,
                None,
                None,
                None,
                None,
            )

        return (
            record.target.enterprise_id,
            record.target.business_stream_id,
            record.target.service_id,
            json.dumps(
                list(record.target.component_ids)
            ),
            record.target.environment.value,
        )

    @staticmethod
    def _row_to_record(
        row: tuple[object, ...],
    ) -> RunRecord:
        validation_value = row[8]
        execution_mode = RunExecutionMode(
            str(row[12])
        )

        historical_configuration = None

        if execution_mode == RunExecutionMode.HISTORICAL:
            historical_configuration = (
                HistoricalExecutionConfiguration(
                    degradation_samples=int(row[13]),
                    plateau_samples=int(row[14]),
                    recovery_samples=int(row[15]),
                )
            )

        generation_lifecycle = (
            GenerationLifecycle(str(row[16]))
            if len(row) > 16 and row[16] is not None
            else GenerationLifecycle.BOUNDED
        )

        continuous_configuration = None

        if (
            generation_lifecycle
            == GenerationLifecycle.CONTINUOUS
        ):
            continuous_configuration = (
                ContinuousExecutionConfiguration(
                    stop_mode=ContinuousStopMode(
                        str(row[17])
                    ),
                    duration_seconds=(
                        int(row[18])
                        if len(row) > 18 and row[18] is not None
                        else None
                    ),
                )
            )
        elif (
            len(row) > 17
            and (row[17] is not None or (len(row) > 18 and row[18] is not None))
        ):
            raise ValueError(
                "Bounded Run cannot contain "
                "continuous execution configuration."
            )

        target = SQLiteRunStore._target_from_row(
            row
        )

        return RunRecord(
            run_id=str(row[0]),
            scenario_id=str(row[1]),
            change_id=str(row[2]),
            status=RunStatus(str(row[3])),
            started_at=datetime.fromisoformat(
                str(row[4])
            ),
            completed_at=(
                datetime.fromisoformat(
                    str(row[5])
                )
                if row[5] is not None
                else None
            ),
            current_state=OperationalState(
                str(row[6])
            ),
            event_count=int(row[7]),
            validation_passed=(
                bool(validation_value)
                if validation_value is not None
                else None
            ),
            random_seed=int(row[9]),
            event_interval_seconds=float(
                row[10]
            ),
            target=target,
            error_message=(
                str(row[11])
                if row[11] is not None
                else None
            ),
            execution_mode=execution_mode,
            historical_configuration=(
                historical_configuration
            ),
            generation_lifecycle=(
                generation_lifecycle
            ),
            continuous_configuration=(
                continuous_configuration
            ),
        )

    @staticmethod
    def _target_from_row(
        row: tuple[object, ...],
    ) -> RunTargetSnapshot | None:
        if len(row) <= 19:
            return None

        if len(row) < 24:
            raise ValueError(
                "Persisted Run target snapshot "
                "columns are incomplete."
            )

        target_values = row[19:24]

        if all(
            value is None
            for value in target_values
        ):
            return None

        if any(
            value is None
            for value in target_values
        ):
            raise ValueError(
                "Persisted Run target snapshot "
                "is incomplete."
            )

        try:
            component_ids = json.loads(
                str(target_values[3])
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Persisted Run target component IDs "
                "are invalid."
            ) from exc

        if (
            not isinstance(component_ids, list)
            or not all(
                isinstance(component_id, str)
                for component_id in component_ids
            )
        ):
            raise ValueError(
                "Persisted Run target component IDs "
                "must be a list of strings."
            )

        return RunTargetSnapshot(
            enterprise_id=str(target_values[0]),
            business_stream_id=str(
                target_values[1]
            ),
            service_id=str(target_values[2]),
            component_ids=tuple(component_ids),
            environment=Environment(
                str(target_values[4])
            ),
        )

    @staticmethod
    def _datetime_to_text(
        value: datetime,
    ) -> str:
        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Run timestamps must be timezone-aware."
            )

        return value.astimezone(
            UTC
        ).isoformat()

    @staticmethod
    def _validate_record(
        record: RunRecord,
    ) -> None:
        if not record.run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        if not record.scenario_id.strip():
            raise ValueError(
                "Scenario ID is required."
            )

        if not record.change_id.strip():
            raise ValueError(
                "Change ID is required."
            )

        if record.event_count < 0:
            raise ValueError(
                "Event count cannot be negative."
            )

        if record.event_interval_seconds <= 0:
            raise ValueError(
                "Event interval must be greater than zero."
            )

        if (
            record.execution_mode
            == RunExecutionMode.HISTORICAL
            and record.historical_configuration is None
        ):
            raise ValueError(
                "Historical Runs require a "
                "historical execution configuration."
            )

        if (
            record.execution_mode
            != RunExecutionMode.HISTORICAL
            and record.historical_configuration is not None
        ):
            raise ValueError(
                "Historical execution configuration "
                "cannot be stored for a Standard Run."
            )

        if (
            record.generation_lifecycle
            == GenerationLifecycle.BOUNDED
            and record.continuous_configuration is not None
        ):
            raise ValueError(
                "Bounded Runs cannot contain "
                "continuous execution configuration."
            )

        if (
            record.generation_lifecycle
            == GenerationLifecycle.CONTINUOUS
            and record.continuous_configuration is None
        ):
            raise ValueError(
                "Continuous Runs require "
                "continuous execution configuration."
            )

        SQLiteRunStore._datetime_to_text(
            record.started_at
        )

        if record.completed_at is not None:
            SQLiteRunStore._datetime_to_text(
                record.completed_at
            )

    def _require_started(self) -> None:
        if not self._started:
            raise RuntimeError(
                "SQLiteRunStore is not started."
            )
