import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.configuration import (
    DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION,
)
from synthetic_ops_generator.control.models import (
    RunExecutionMode,
    RunRecord,
    RunStatus,
)
from synthetic_ops_generator.control.service import (
    ControlService,
    RunNotFoundError,
    RunNotReplayableError,
    RunNotStoppableError,
    ScenarioNotFoundError,
)
from synthetic_ops_generator.control.sqlite_run_store import (
    SQLiteRunStore,
)
from synthetic_ops_generator.core.sqlite_identifiers import (
    SQLiteIdFactory,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.history.executor import (
    HistoricalRunExecutor,
)
from synthetic_ops_generator.publishers.base import (
    EventPublisher,
)
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.publishers.retention import (
    RetentionPublisher,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


class BlockingAfterFirstPublisher(
    EventPublisher
):
    """
    Publishes one event normally, then blocks
    before publishing the second event.

    This provides a deterministic cancellation
    point for Stop Run tests.
    """

    def __init__(
        self,
        delegate: EventPublisher,
    ) -> None:
        self._delegate = delegate
        self._published_count = 0

        self.blocked = asyncio.Event()
        self._release = asyncio.Event()

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        if self._published_count >= 1:
            self.blocked.set()

            await self._release.wait()

        await self._delegate.publish(
            event
        )

        self._published_count += 1


class BlockingAfterHistoricalSamplePublisher(
    EventPublisher
):
    """
    Publishes one complete historical sample
    of three Metric events, then blocks before
    the next Event.

    This provides a deterministic cancellation
    point after persisted historical progress.
    """

    def __init__(
        self,
        delegate: EventPublisher,
    ) -> None:
        self._delegate = delegate
        self._published_count = 0

        self.blocked = asyncio.Event()
        self._release = asyncio.Event()

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        if self._published_count >= 3:
            self.blocked.set()

            await self._release.wait()

        await self._delegate.publish(
            event
        )

        self._published_count += 1


class FailingAfterHistoricalSamplePublisher(
    EventPublisher
):
    """
    Publishes one complete historical sample,
    then fails before the next Event.
    """

    def __init__(
        self,
        delegate: EventPublisher,
    ) -> None:
        self._delegate = delegate
        self._published_count = 0

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        if self._published_count >= 3:
            raise RuntimeError(
                "historical publisher failed"
            )

        await self._delegate.publish(
            event
        )

        self._published_count += 1


async def wait_for_terminal_run(
    service: ControlService,
    run_id: str,
    *,
    timeout_seconds: float = 5.0,
) -> RunRecord:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds

    while True:
        record = await service.get_run(
            run_id
        )

        if record.status != RunStatus.RUNNING:
            return record

        if loop.time() >= deadline:
            raise AssertionError(
                f"Run '{run_id}' did not reach "
                "a terminal state within "
                f"{timeout_seconds} seconds."
            )

        await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_control_service_executes_and_retains_bank_01(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        result = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        assert result.scenario_id == "BANK-01"
        assert result.run_id == "RUN0000001"
        assert result.change_id == "CHG0000001"
        assert result.status == RunStatus.RUNNING

        record = await wait_for_terminal_run(
            service,
            result.run_id,
        )

        retained_events = (
            await store.get_run_events(
                result.run_id
            )
        )

        assert len(retained_events) == 32

        assert all(
            event.run_id == result.run_id
            for event in retained_events
        )

        assert record.status == RunStatus.COMPLETED
        assert (
            record.current_state
            == OperationalState.COMPLETED
        )
        assert record.event_count == 32
        assert record.validation_passed is True
        assert record.completed_at is not None

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_queries_run_events_by_source_domain(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        result = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        await wait_for_terminal_run(
            service,
            result.run_id,
        )

        events = await service.query_run_events(
            result.run_id,
            source_domain=SourceDomain.METRIC,
        )

        assert events

        assert {
            event.run_id
            for event in events
        } == {result.run_id}

        assert {
            event.source_domain
            for event in events
        } == {SourceDomain.METRIC}

        assert [
            event.sequence_number
            for event in events
        ] == sorted(
            event.sequence_number
            for event in events
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_uses_persistent_run_ids(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        first = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        second = await service.start_run(
            scenario_id="INS-01",
            random_seed=42,
        )

        assert first.run_id == "RUN0000001"
        assert second.run_id == "RUN0000002"

        assert first.change_id == "CHG0000001"
        assert second.change_id == "CHG0000002"

        first_record = await wait_for_terminal_run(
            service,
            first.run_id,
        )

        second_record = await wait_for_terminal_run(
            service,
            second.run_id,
        )

        assert (
            first_record.status
            == RunStatus.COMPLETED
        )
        assert (
            second_record.status
            == RunStatus.COMPLETED
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_rejects_unknown_scenario(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        with pytest.raises(
            ScenarioNotFoundError,
            match="Scenario 'UNKNOWN' was not found",
        ):
            await service.start_run(
                scenario_id="UNKNOWN",
                random_seed=42,
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_gets_persisted_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        result = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        record = await wait_for_terminal_run(
            service,
            result.run_id,
        )

        assert record.run_id == result.run_id
        assert record.scenario_id == "BANK-01"
        assert record.status == RunStatus.COMPLETED
        assert record.event_count == 32

        assert record.target is not None

        assert (
            record.target.enterprise_id
            == "bank_alpha"
        )

        assert (
            record.target.business_stream_id
            == "payments"
        )

        assert (
            record.target.service_id
            == "payment_service"
        )

        assert record.target.component_ids == (
            "payment_api",
            "payment_database",
            "payment_worker",
        )

        assert (
            record.target.environment.value
            == "production"
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_replays_retained_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        replay_publisher = InMemoryPublisher()

        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=replay_publisher,
            active_run_manager=active_run_manager,
        )

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        record = await wait_for_terminal_run(
            service,
            started.run_id,
        )

        assert record.status == RunStatus.COMPLETED

        retained_before = (
            await store.get_run_events(
                started.run_id
            )
        )

        replayed = await service.replay_run(
            started.run_id
        )

        retained_after = (
            await store.get_run_events(
                started.run_id
            )
        )

        assert replayed.run_id == started.run_id
        assert replayed.scenario_id == "BANK-01"
        assert replayed.replayed_event_count == 32

        assert tuple(
            replay_publisher.events
        ) == tuple(
            retained_before
        )

        assert tuple(
            retained_after
        ) == tuple(
            retained_before
        )

        assert len(retained_after) == 32

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_replay_rejects_unknown_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        with pytest.raises(
            RunNotFoundError,
            match=(
                "Run 'RUN9999999' "
                "was not found"
            ),
        ):
            await service.replay_run(
                "RUN9999999"
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_rejects_replay_of_running_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        running_record = RunRecord(
            run_id="RUN0000001",
            scenario_id="BANK-01",
            change_id="CHG0000001",
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            completed_at=None,
            current_state=(
                OperationalState.INITIALISING
            ),
            event_count=0,
            validation_passed=None,
            random_seed=42,
            event_interval_seconds=5.0,
        )

        await run_store.create(
            running_record
        )

        with pytest.raises(
            RunNotReplayableError,
            match=(
                "Run 'RUN0000001' cannot be "
                "replayed while it is running."
            ),
        ):
            await service.replay_run(
                "RUN0000001"
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_rejects_stop_of_completed_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        completed = await wait_for_terminal_run(
            service,
            started.run_id,
        )

        assert (
            completed.status
            == RunStatus.COMPLETED
        )

        with pytest.raises(
            RunNotStoppableError,
            match=(
                "Run 'RUN0000001' cannot be "
                "stopped because its status "
                "is 'completed'."
            ),
        ):
            await service.stop_run(
                started.run_id
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_rejects_running_record_without_active_task(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        running_record = RunRecord(
            run_id="RUN0000001",
            scenario_id="BANK-01",
            change_id="CHG0000001",
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            completed_at=None,
            current_state=(
                OperationalState.INITIALISING
            ),
            event_count=0,
            validation_passed=None,
            random_seed=42,
            event_interval_seconds=5.0,
        )

        await run_store.create(
            running_record
        )

        with pytest.raises(
            RunNotStoppableError,
            match=(
                "Run 'RUN0000001' is marked "
                "as running but has no active "
                "execution task."
            ),
        ):
            await service.stop_run(
                "RUN0000001"
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_stops_running_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()
    blocking_publisher = BlockingAfterFirstPublisher(
        delegate=RetentionPublisher(store=store)
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
            execution_publisher_factory=lambda: blocking_publisher,
        )

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        await blocking_publisher.blocked.wait()

        stop_result = await service.stop_run(
            started.run_id
        )

        record = await service.get_run(
            started.run_id
        )

        assert stop_result.run_id == started.run_id
        assert stop_result.scenario_id == "BANK-01"
        assert stop_result.status == RunStatus.STOPPED
        assert stop_result.event_count == 1

        assert (
            record.status
            == RunStatus.STOPPED
        )
        assert record.event_count == 1
        assert (
            record.validation_passed
            is None
        )
        assert record.completed_at is not None

        assert not (
            active_run_manager.is_active(
                started.run_id
            )
        )

        retained_events = (
            await store.get_run_events(
                started.run_id
            )
        )

        assert len(retained_events) == 1

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_reconciles_orphaned_runs(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT
                / "enterprises"
            ),
            generator_factory=(
                GeneratorFactory(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=(
                InMemoryPublisher()
            ),
            active_run_manager=(
                active_run_manager
            ),
        )

        running_record = RunRecord(
            run_id="RUN0000001",
            scenario_id="BANK-01",
            change_id="CHG0000001",
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

        await run_store.create(
            running_record
        )

        reconciled = (
            await service.reconcile_orphaned_runs()
        )

        assert reconciled == 1

        record = await service.get_run(
            "RUN0000001"
        )

        assert (
            record.status
            == RunStatus.FAILED
        )
        assert (
            record.current_state
            == OperationalState.IMPLEMENTING
        )
        assert record.event_count == 0
        assert (
            record.validation_passed
            is None
        )
        assert record.completed_at is not None
        assert record.error_message == (
            "Run interrupted by "
            "application restart."
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_orphan_reconciliation_is_idempotent(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "events.sqlite3"
        )
    )

    run_store = SQLiteRunStore(
        database_path=(
            tmp_path
            / "runs.sqlite3"
        )
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT
                / "enterprises"
            ),
            generator_factory=(
                GeneratorFactory(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=(
                InMemoryPublisher()
            ),
            active_run_manager=(
                active_run_manager
            ),
        )

        running_record = RunRecord(
            run_id="RUN0000001",
            scenario_id="BANK-01",
            change_id="CHG0000001",
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            completed_at=None,
            current_state=(
                OperationalState.INITIALISING
            ),
            event_count=0,
            validation_passed=None,
            random_seed=42,
            event_interval_seconds=5.0,
        )

        await run_store.create(
            running_record
        )

        first = (
            await service.reconcile_orphaned_runs()
        )

        second = (
            await service.reconcile_orphaned_runs()
        )

        assert first == 1
        assert second == 0

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_persists_live_progress_during_execution(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "events.sqlite3"
        )
    )

    run_store = SQLiteRunStore(
        database_path=(
            tmp_path
            / "runs.sqlite3"
        )
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    blocking_publisher = (
        BlockingAfterFirstPublisher(
            delegate=(
                RetentionPublisher(
                    store=store
                )
            )
        )
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT
                / "enterprises"
            ),
            generator_factory=(
                GeneratorFactory(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=(
                InMemoryPublisher()
            ),
            active_run_manager=(
                active_run_manager
            ),
            execution_publisher_factory=(
                lambda: blocking_publisher
            ),
        )

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
        )

        assert (
            started.status
            == RunStatus.RUNNING
        )

        await asyncio.wait_for(
            blocking_publisher.blocked.wait(),
            timeout=5.0,
        )

        live_record = await service.get_run(
            started.run_id
        )

        assert (
            live_record.status
            == RunStatus.RUNNING
        )

        assert (
            live_record.current_state
            != OperationalState.INITIALISING
        )

        assert (
            live_record.completed_at
            is None
        )

        assert (
            live_record.validation_passed
            is None
        )

        assert (
            active_run_manager.is_active(
                started.run_id
            )
        )

        stopped = await service.stop_run(
            started.run_id
        )

        assert (
            stopped.status
            == RunStatus.STOPPED
        )

        final_record = await service.get_run(
            started.run_id
        )

        assert (
            final_record.status
            == RunStatus.STOPPED
        )

        assert (
            final_record.current_state
            == live_record.current_state
        )

        assert (
            final_record.completed_at
            is not None
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_executes_historical_managed_run(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    store = SQLiteEventStore(
        database_path=(
            data_root
            / "events.sqlite3"
        )
    )

    run_store = SQLiteRunStore(
        database_path=(
            data_root
            / "runs.sqlite3"
        )
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT
                / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            historical_run_executor=(
                HistoricalRunExecutor(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=(
                active_run_manager
            ),
        )

        result = await service.start_run(
            scenario_id="BANK-02",
            random_seed=42,
            execution_mode=(
                RunExecutionMode.HISTORICAL
            ),
        )

        assert (
            result.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        record = await wait_for_terminal_run(
            service,
            result.run_id,
        )

        retained_events = (
            await store.get_run_events(
                result.run_id
            )
        )

        assert record.status == (
            RunStatus.COMPLETED
        )

        assert (
            record.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        assert (
            record.current_state
            == OperationalState.COMPLETED
        )

        assert record.event_count == 48

        assert (
            record.validation_passed
            is None
        )

        assert len(retained_events) == 48

        assert all(
            event.event_type
            == "metric.observed"
            for event in retained_events
        )

        assert all(
            "historical"
            in event.data["metric"]
            for event in retained_events
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_executes_insurance_historical_managed_run(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    store = SQLiteEventStore(
        database_path=(
            data_root
            / "events.sqlite3"
        )
    )

    run_store = SQLiteRunStore(
        database_path=(
            data_root
            / "runs.sqlite3"
        )
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT
                / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            historical_run_executor=(
                HistoricalRunExecutor(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        started = await service.start_run(
            scenario_id="INS-02",
            random_seed=42,
            execution_mode=(
                RunExecutionMode.HISTORICAL
            ),
        )

        assert (
            started.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        record = await wait_for_terminal_run(
            service,
            started.run_id,
        )

        retained_events = (
            await store.get_run_events(
                started.run_id
            )
        )

        assert (
            record.status
            == RunStatus.COMPLETED
        )

        assert (
            record.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        assert (
            record.current_state
            == OperationalState.COMPLETED
        )

        assert record.event_count == 48

        assert (
            record.validation_passed
            is None
        )

        assert len(retained_events) == 48

        assert all(
            event.scenario_id == "INS-02"
            for event in retained_events
        )

        assert all(
            event.event_type
            == "metric.observed"
            for event in retained_events
        )

        assert all(
            "historical"
            in event.data["metric"]
            for event in retained_events
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_stops_historical_managed_run_after_sample(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    store = SQLiteEventStore(
        database_path=(
            data_root
            / "events.sqlite3"
        )
    )

    run_store = SQLiteRunStore(
        database_path=(
            data_root
            / "runs.sqlite3"
        )
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    blocking_publisher = (
        BlockingAfterHistoricalSamplePublisher(
            delegate=(
                RetentionPublisher(
                    store=store
                )
            )
        )
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT
                / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            historical_run_executor=(
                HistoricalRunExecutor(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
            execution_publisher_factory=(
                lambda: blocking_publisher
            ),
        )

        started = await service.start_run(
            scenario_id="BANK-02",
            random_seed=42,
            execution_mode=(
                RunExecutionMode.HISTORICAL
            ),
        )

        await asyncio.wait_for(
            blocking_publisher.blocked.wait(),
            timeout=5.0,
        )

        live_record = await service.get_run(
            started.run_id
        )

        assert (
            live_record.status
            == RunStatus.RUNNING
        )

        assert live_record.event_count == 3

        assert (
            live_record.current_state
            == OperationalState.NORMAL
        )

        stop_result = await service.stop_run(
            started.run_id
        )

        stopped_record = await service.get_run(
            started.run_id
        )

        retained_events = (
            await store.get_run_events(
                started.run_id
            )
        )

        assert (
            stop_result.status
            == RunStatus.STOPPED
        )

        assert stop_result.event_count == 3

        assert (
            stopped_record.status
            == RunStatus.STOPPED
        )

        assert (
            stopped_record.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        assert (
            stopped_record.current_state
            == OperationalState.NORMAL
        )

        assert stopped_record.event_count == 3

        assert (
            stopped_record.validation_passed
            is None
        )

        assert (
            stopped_record.completed_at
            is not None
        )

        assert len(retained_events) == 3

        assert not (
            active_run_manager.is_active(
                started.run_id
            )
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_handles_historical_managed_run_failure(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "runs"

    store = SQLiteEventStore(
        database_path=(
            data_root
            / "events.sqlite3"
        )
    )

    run_store = SQLiteRunStore(
        database_path=(
            data_root
            / "runs.sqlite3"
        )
    )

    await store.start()
    await run_store.start()

    active_run_manager = (
        ActiveRunManager()
    )

    failing_publisher = (
        FailingAfterHistoricalSamplePublisher(
            delegate=(
                RetentionPublisher(
                    store=store
                )
            )
        )
    )

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            historical_run_executor=(
                HistoricalRunExecutor(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
            execution_publisher_factory=(
                lambda: failing_publisher
            ),
        )

        started = await service.start_run(
            scenario_id="BANK-02",
            random_seed=42,
            execution_mode=(
                RunExecutionMode.HISTORICAL
            ),
        )

        failed_record = await wait_for_terminal_run(
            service,
            started.run_id,
        )

        retained_events = (
            await store.get_run_events(
                started.run_id
            )
        )

        assert (
            failed_record.status
            == RunStatus.FAILED
        )

        assert (
            failed_record.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        assert (
            failed_record.current_state
            == OperationalState.NORMAL
        )

        assert failed_record.event_count == 3

        assert (
            failed_record.validation_passed
            is None
        )

        assert (
            failed_record.completed_at
            is not None
        )

        assert failed_record.error_message == (
            "historical publisher failed"
        )

        assert len(retained_events) == 3

        assert not (
            active_run_manager.is_active(
                started.run_id
            )
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_control_service_replays_completed_historical_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()
    replay_publisher = InMemoryPublisher()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            historical_run_executor=(
                HistoricalRunExecutor(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=replay_publisher,
            active_run_manager=active_run_manager,
        )

        started = await service.start_run(
            scenario_id="BANK-02",
            random_seed=42,
            execution_mode=(
                RunExecutionMode.HISTORICAL
            ),
        )

        completed = await wait_for_terminal_run(
            service,
            started.run_id,
        )

        assert (
            completed.status
            == RunStatus.COMPLETED
        )

        retained_events = (
            await store.get_run_events(
                started.run_id
            )
        )

        replayed = await service.replay_run(
            started.run_id
        )

        assert replayed.run_id == (
            started.run_id
        )

        assert (
            replayed.scenario_id
            == "BANK-02"
        )

        assert (
            replayed.replayed_event_count
            == 48
        )

        assert len(retained_events) == 48

        assert (
            replay_publisher.events
            == list(retained_events)
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_historical_orphaned_run_is_reconciled_as_failed(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )

    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    active_run_manager = ActiveRunManager()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            historical_run_executor=(
                HistoricalRunExecutor(
                    config_root=CONFIG_ROOT
                )
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path
                    / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
            active_run_manager=active_run_manager,
        )

        running_record = RunRecord(
            run_id="RUN0000001",
            scenario_id="BANK-02",
            change_id="CHG0000001",
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            completed_at=None,
            current_state=(
                OperationalState.OBSERVING
            ),
            event_count=0,
            validation_passed=None,
            random_seed=42,
            event_interval_seconds=5.0,
            execution_mode=(
                RunExecutionMode.HISTORICAL
            ),
            historical_configuration=(
                DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION
            ),
        )

        await run_store.create(
            running_record
        )

        reconciled = (
            await service.reconcile_orphaned_runs()
        )

        assert reconciled == 1

        record = await service.get_run(
            "RUN0000001"
        )

        assert (
            record.status
            == RunStatus.FAILED
        )

        assert (
            record.execution_mode
            == RunExecutionMode.HISTORICAL
        )

        assert (
            record.current_state
            == OperationalState.OBSERVING
        )

        assert record.event_count == 0

        assert (
            record.validation_passed
            is None
        )

        assert record.completed_at is not None

        assert record.error_message == (
            "Run interrupted by "
            "application restart."
        )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_get_run_events_requires_existing_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
        )

        with pytest.raises(
            RunNotFoundError
        ):
            await service.get_run_events(
                "RUN9999999"
            )

    finally:
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_query_run_events_requires_existing_run(
    tmp_path: Path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.sqlite3"
    )
    run_store = SQLiteRunStore(
        database_path=tmp_path / "runs.sqlite3"
    )

    await store.start()
    await run_store.start()

    try:
        service = ControlService(
            catalogue=ScenarioCatalogue(
                CONFIG_ROOT / "scenarios"
            ),
            enterprise_root=(
                CONFIG_ROOT / "enterprises"
            ),
            generator_factory=GeneratorFactory(
                config_root=CONFIG_ROOT
            ),
            ids=SQLiteIdFactory(
                database_path=(
                    tmp_path / "identifiers.sqlite3"
                )
            ),
            store=store,
            run_store=run_store,
            replay_publisher=InMemoryPublisher(),
        )

        with pytest.raises(
            RunNotFoundError
        ):
            await service.query_run_events(
                "RUN9999999",
                source_domain=SourceDomain.METRIC,
            )

    finally:
        await run_store.stop()
        await store.stop()