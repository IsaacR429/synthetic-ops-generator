import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.models import (
    ReplayExecutionResult,
    RunExecutionMode,
    RunRecord,
    RunStartResult,
    RunStatus,
    StopRunResult,
)
from synthetic_ops_generator.control.run_store import RunStore
from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.history.executor import (
    HistoricalRunExecutor,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.publishers.base import (
    EventPublisher,
)
from synthetic_ops_generator.publishers.retention import (
    RetentionPublisher,
)
from synthetic_ops_generator.replay.service import (
    ReplayService,
)
from synthetic_ops_generator.retention.base import EventStore
from synthetic_ops_generator.scenarios.capabilities import (
    resolve_scenario_execution_capabilities,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)
from synthetic_ops_generator.scenarios.runner import (
    ScenarioRunner,
)
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)


class ScenarioNotFoundError(LookupError):
    pass


class RunNotFoundError(LookupError):
    pass


class RunNotReplayableError(Exception):
    pass


class RunNotStoppableError(RuntimeError):
    pass


class RunExecutionModeNotSupportedError(
    RuntimeError
):
    pass


ExecutionPublisherFactory = Callable[
    [],
    EventPublisher,
]


class ControlService:
    """
    Coordinates configured Scenario execution.

    HTTP concerns are intentionally excluded from this service.
    """

    def __init__(
        self,
        *,
        catalogue: ScenarioCatalogue,
        enterprise_root: str | Path,
        generator_factory: GeneratorFactory,
        ids: IdFactory,
        store: EventStore,
        run_store: RunStore,
        replay_publisher: EventPublisher,
        active_run_manager: ActiveRunManager | None = None,
        execution_publisher_factory: (
            ExecutionPublisherFactory | None
        ) = None,
        historical_run_executor: (
            HistoricalRunExecutor | None
        ) = None,
        event_interval_seconds: float = 5.0,
    ) -> None:
        if event_interval_seconds <= 0:
            raise ValueError(
                "Event interval must be greater than zero."
            )

        self._catalogue = catalogue
        self._enterprise_root = Path(
            enterprise_root
        )
        self._generator_factory = generator_factory
        self._ids = ids
        self._store = store
        self._run_store = run_store
        self._replay_publisher = replay_publisher
        self._active_run_manager = active_run_manager
        self._execution_publisher_factory = (
            execution_publisher_factory
            if execution_publisher_factory is not None
            else self._create_default_execution_publisher
        )
        self._historical_run_executor = (
            historical_run_executor
        )
        self._event_interval_seconds = (
            event_interval_seconds
        )

    def _create_default_execution_publisher(
        self,
    ) -> EventPublisher:
        return RetentionPublisher(
            store=self._store
        )

    async def start_run(
        self,
        *,
        scenario_id: str,
        random_seed: int,
        execution_mode: RunExecutionMode = (
            RunExecutionMode.STANDARD
        ),
    ) -> RunStartResult:
        scenario = self._catalogue.get_scenario(
            scenario_id
        )

        if scenario is None:
            raise ScenarioNotFoundError(
                f"Scenario '{scenario_id}' was not found."
            )

        capabilities = (
            resolve_scenario_execution_capabilities(
                scenario
            )
        )

        if (
            execution_mode
            == RunExecutionMode.HISTORICAL
            and not capabilities.historical_supported
        ):
            raise RunExecutionModeNotSupportedError(
                "Scenario "
                f"'{scenario.scenario_id}' does not "
                "support managed historical execution."
            )

        enterprise_path = (
            self._enterprise_root
            / scenario.target.enterprise_id
        )

        enterprise = load_enterprise_configuration(
            enterprise_path
        )

        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )

        clock = ManualSimulationClock(
            datetime.now(UTC)
        )

        runner = ScenarioRunner(
            ids=self._ids,
            clock=clock,
        )

        context = runner.create_context(
            scenario=scenario,
            enterprise=enterprise,
            random_seed=random_seed,
        )

        run_record = RunRecord(
            run_id=context.run_id,
            scenario_id=scenario.scenario_id,
            change_id=context.chg_id,
            status=RunStatus.RUNNING,
            started_at=context.simulation_time,
            completed_at=None,
            current_state=context.scenario_state,
            event_count=0,
            validation_passed=None,
            random_seed=random_seed,
            event_interval_seconds=(
                self._event_interval_seconds
            ),
            execution_mode=execution_mode,
        )

        await self._run_store.create(
            run_record
        )

        async def _execute() -> None:
            try:
                publisher = (
                    self._execution_publisher_factory()
                )

                async def persist_progress(
                    state: OperationalState,
                    event_count: int,
                ) -> None:
                    await self._persist_run_progress(
                        context.run_id,
                        state,
                        event_count,
                    )

                if (
                    execution_mode
                    == RunExecutionMode.HISTORICAL
                ):
                    if self._historical_run_executor is None:
                        raise RuntimeError(
                            "Historical execution is not configured."
                        )

                    await self._historical_run_executor.execute(
                        scenario=scenario,
                        enterprise=enterprise,
                        context=context,
                        ids=self._ids,
                        publisher=publisher,
                        anchor_time=context.simulation_time,
                        curve_spec=(
                            PerturbationCurveSpec(
                                degradation_samples=4,
                                plateau_samples=2,
                                recovery_samples=4,
                            )
                        ),
                        progress_observer=persist_progress,
                    )

                    latest_record = (
                        await self._run_store.get(
                            context.run_id
                        )
                    )

                    if latest_record is None:
                        raise RuntimeError(
                            f"Run '{context.run_id}' disappeared "
                            "during historical execution."
                        )

                    completed_record = replace(
                        latest_record,
                        status=RunStatus.COMPLETED,
                        completed_at=datetime.now(UTC),
                        current_state=(
                            OperationalState.COMPLETED
                        ),
                        validation_passed=None,
                    )

                    await self._run_store.update(
                        completed_record
                    )

                    return

                random_source = SimulationRandom(
                    context.random_seed
                )

                generators = self._generator_factory.build(
                    scenario=scenario,
                    enterprise=enterprise,
                    ids=self._ids,
                    random_source=random_source,
                    event_history=runner.event_history,
                )

                await runner.execute(
                    scenario=scenario,
                    context=context,
                    generators=generators,
                    publisher=publisher,
                    progress_observer=persist_progress,
                    event_interval_seconds=(
                        self._event_interval_seconds
                    ),
                )

                validation_report = (
                    CrossSourceValidator().validate(
                        events=runner.event_history,
                        context=context,
                        enterprise=enterprise,
                    )
                )

            except asyncio.CancelledError:
                if (
                    execution_mode
                    == RunExecutionMode.HISTORICAL
                ):
                    latest_record = (
                        await self._latest_persisted_progress(
                            context.run_id
                        )
                    )

                    stopped_record = replace(
                        latest_record,
                        status=RunStatus.STOPPED,
                        completed_at=datetime.now(UTC),
                        validation_passed=None,
                    )
                else:
                    stopped_record = replace(
                        run_record,
                        status=RunStatus.STOPPED,
                        completed_at=datetime.now(UTC),
                        current_state=context.scenario_state,
                        event_count=len(
                            runner.event_history
                        ),
                        validation_passed=None,
                    )

                await self._run_store.update(
                    stopped_record
                )

                raise

            except Exception as exc:
                if (
                    execution_mode
                    == RunExecutionMode.HISTORICAL
                ):
                    latest_record = (
                        await self._latest_persisted_progress(
                            context.run_id
                        )
                    )

                    failed_record = replace(
                        latest_record,
                        status=RunStatus.FAILED,
                        completed_at=datetime.now(UTC),
                        validation_passed=None,
                        error_message=str(exc),
                    )
                else:
                    failed_record = replace(
                        run_record,
                        status=RunStatus.FAILED,
                        completed_at=datetime.now(UTC),
                        current_state=context.scenario_state,
                        event_count=len(
                            runner.event_history
                        ),
                        validation_passed=None,
                        error_message=str(exc),
                    )

                await self._run_store.update(
                    failed_record
                )

                raise

            completed_record = replace(
                run_record,
                status=RunStatus.COMPLETED,
                completed_at=datetime.now(UTC),
                current_state=context.scenario_state,
                event_count=len(
                    runner.event_history
                ),
                validation_passed=(
                    validation_report.is_valid
                ),
            )

            await self._run_store.update(
                completed_record
            )

        if self._active_run_manager is not None:
            self._active_run_manager.start(
                context.run_id,
                _execute,
            )
        else:
            await _execute()

        return RunStartResult(
            scenario_id=scenario.scenario_id,
            run_id=context.run_id,
            change_id=context.chg_id,
            status=RunStatus.RUNNING,
            execution_mode=execution_mode,
        )

    async def _latest_persisted_progress(
        self,
        run_id: str,
    ) -> RunRecord:
        record = await self._run_store.get(
            run_id
        )

        if record is None:
            raise RuntimeError(
                f"Run '{run_id}' disappeared "
                "during execution."
            )

        return record

    async def get_run(
        self,
        run_id: str,
    ) -> RunRecord:
        record = await self._run_store.get(
            run_id
        )

        if record is None:
            raise RunNotFoundError(
                f"Run '{run_id}' was not found."
            )

        return record

    async def _persist_run_progress(
        self,
        run_id: str,
        state: OperationalState,
        event_count: int,
    ) -> None:
        record = await self._run_store.get(
            run_id
        )

        if record is None:
            raise RuntimeError(
                f"Run '{run_id}' disappeared "
                "during execution."
            )

        if record.status != RunStatus.RUNNING:
            return

        await self._run_store.update(
            replace(
                record,
                current_state=state,
                event_count=event_count,
            )
        )

    async def reconcile_orphaned_runs(
        self,
    ) -> int:
        running_records = (
            await self._run_store.list_by_status(
                RunStatus.RUNNING
            )
        )

        reconciled_count = 0

        for record in running_records:
            if (
                self._active_run_manager is not None
                and self._active_run_manager.is_active(
                    record.run_id
                )
            ):
                continue

            retained_events = (
                await self._store.get_run_events(
                    record.run_id
                )
            )

            failed_record = replace(
                record,
                status=RunStatus.FAILED,
                completed_at=datetime.now(UTC),
                event_count=len(
                    retained_events
                ),
                validation_passed=None,
                error_message=(
                    "Run interrupted by "
                    "application restart."
                ),
            )

            await self._run_store.update(
                failed_record
            )

            reconciled_count += 1

        return reconciled_count

    async def stop_run(
        self,
        run_id: str,
    ) -> StopRunResult:
        record = await self.get_run(
            run_id
        )

        if record.status != RunStatus.RUNNING:
            raise RunNotStoppableError(
                f"Run '{run_id}' cannot be stopped "
                f"because its status is "
                f"'{record.status.value}'."
            )

        stopped = await self._active_run_manager.stop(
            run_id
        )

        if not stopped:
            raise RunNotStoppableError(
                f"Run '{run_id}' is marked as running "
                "but has no active execution task."
            )

        stopped_record = await self.get_run(
            run_id
        )

        if stopped_record.status != RunStatus.STOPPED:
            raise RuntimeError(
                f"Run '{run_id}' was cancelled but "
                "did not persist the stopped state."
            )

        return StopRunResult(
            run_id=stopped_record.run_id,
            scenario_id=stopped_record.scenario_id,
            status=stopped_record.status,
            event_count=stopped_record.event_count,
        )

    async def replay_run(
        self,
        run_id: str,
    ) -> ReplayExecutionResult:
        record = await self.get_run(
            run_id
        )

        if record.status == RunStatus.RUNNING:
            raise RunNotReplayableError(
                f"Run '{run_id}' cannot be replayed "
                "while it is running."
            )

        replay_service = ReplayService(
            store=self._store,
            publisher=self._replay_publisher,
        )

        replayed_event_count = (
            await replay_service.replay_run(
                record.run_id
            )
        )

        return ReplayExecutionResult(
            run_id=record.run_id,
            scenario_id=record.scenario_id,
            replayed_event_count=(
                replayed_event_count
            ),
        )