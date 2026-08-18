import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.config.runtime import (
    load_generator_runtime_configuration,
    resolve_source_frequency_configuration,
)
from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.configuration import (
    DEFAULT_CONTINUOUS_EXECUTION_CONFIGURATION,
    DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION,
    ContinuousExecutionConfiguration,
    ContinuousStopMode,
    GenerationLifecycle,
    HistoricalExecutionConfiguration,
)
from synthetic_ops_generator.control.models import (
    ReplayExecutionResult,
    RunExecutionMode,
    RunRecord,
    RunStartResult,
    RunStatus,
    RunTargetSnapshot,
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
from synthetic_ops_generator.publishers.retention import (
    RetentionPublisher,
)
from synthetic_ops_generator.replay.service import (
    ReplayService,
)
from synthetic_ops_generator.retention.base import EventStore
from synthetic_ops_generator.retention.query import EventQuery
from synthetic_ops_generator.scenarios.capabilities import (
    resolve_scenario_execution_capabilities,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)
from synthetic_ops_generator.scenarios.continuous import (
    ContinuousSourceBinding,
    ContinuousSourceScheduler,
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

RunProgressObserver = Callable[
    [OperationalState, int],
    Awaitable[None],
]


class _ContinuousProgressPublisher(
    EventPublisher
):
    def __init__(
        self,
        *,
        delegate: EventPublisher,
        state: OperationalState,
        initial_event_count: int,
        progress_observer: RunProgressObserver,
    ) -> None:
        self._delegate = delegate
        self._state = state
        self._event_count = initial_event_count
        self._progress_observer = (
            progress_observer
        )

    async def publish(
        self,
        event: GeneratedEvent,
    ) -> None:
        operation = asyncio.create_task(
            self._publish_and_persist(
                event
            )
        )

        try:
            await asyncio.shield(
                operation
            )

        except asyncio.CancelledError:
            # Publishing the Event and persisting
            # its Run count form one accounting
            # boundary. Finish an in-flight Event
            # before propagating Stop cancellation.
            await operation
            raise

    async def _publish_and_persist(
        self,
        event: GeneratedEvent,
    ) -> None:
        await self._delegate.publish(
            event
        )

        self._event_count += 1

        await self._progress_observer(
            self._state,
            self._event_count,
        )


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
        historical_configuration: (
            HistoricalExecutionConfiguration | None
        ) = None,
        generation_lifecycle: GenerationLifecycle = (
            GenerationLifecycle.BOUNDED
        ),
        continuous_configuration: (
            ContinuousExecutionConfiguration | None
        ) = None,
    ) -> RunStartResult:
        scenario = self._catalogue.get_scenario(
            scenario_id
        )

        if scenario is None:
            raise ScenarioNotFoundError(
                f"Scenario '{scenario_id}' was not found."
            )

        if (
            generation_lifecycle
            == GenerationLifecycle.CONTINUOUS
            and execution_mode
            == RunExecutionMode.HISTORICAL
        ):
            raise RunExecutionModeNotSupportedError(
                "Continuous lifecycle is not supported "
                "for historical execution."
            )

        if (
            generation_lifecycle
            != GenerationLifecycle.CONTINUOUS
            and continuous_configuration is not None
        ):
            raise ValueError(
                "Continuous configuration can only "
                "be supplied for continuous generation."
            )

        resolved_continuous_configuration = (
            continuous_configuration
            if continuous_configuration is not None
            else (
                DEFAULT_CONTINUOUS_EXECUTION_CONFIGURATION
                if (
                    generation_lifecycle
                    == GenerationLifecycle.CONTINUOUS
                )
                else None
            )
        )

        if (
            generation_lifecycle
            == GenerationLifecycle.CONTINUOUS
        ):
            assert (
                resolved_continuous_configuration
                is not None
            )

            if (
                resolved_continuous_configuration.stop_mode
                != ContinuousStopMode.MANUAL
            ):
                raise RunExecutionModeNotSupportedError(
                    "Duration-based continuous "
                    "execution is not supported yet."
                )

            continuous_active_state = (
                scenario.state_sequence[-2]
            )

            active_continuous_behaviours = [
                behaviour
                for behaviour in scenario.behaviours
                if (
                    behaviour.continuous
                    and behaviour.during_state
                    == continuous_active_state
                )
            ]

            if not active_continuous_behaviours:
                raise RunExecutionModeNotSupportedError(
                    "Scenario "
                    f"'{scenario.scenario_id}' does not "
                    "define continuous behaviour in "
                    "its final active state."
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

        if (
            execution_mode
            != RunExecutionMode.HISTORICAL
            and historical_configuration is not None
        ):
            raise ValueError(
                "Historical configuration can only "
                "be supplied for historical execution."
            )

        resolved_historical_configuration = (
            historical_configuration
            if historical_configuration is not None
            else (
                DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION
                if (
                    execution_mode
                    == RunExecutionMode.HISTORICAL
                )
                else None
            )
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
            target=RunTargetSnapshot(
                enterprise_id=(
                    scenario.target.enterprise_id
                ),
                business_stream_id=(
                    scenario.target.business_stream_id
                ),
                service_id=(
                    scenario.target.service_id
                ),
                component_ids=tuple(
                    scenario.target.component_ids
                ),
                environment=(
                    scenario.target.environment
                ),
            ),
            execution_mode=execution_mode,
            historical_configuration=(
                resolved_historical_configuration
            ),
            generation_lifecycle=(
                generation_lifecycle
            ),
            continuous_configuration=(
                resolved_continuous_configuration
            ),
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

                    assert resolved_historical_configuration is not None

                    await self._historical_run_executor.execute(
                        scenario=scenario,
                        enterprise=enterprise,
                        context=context,
                        ids=self._ids,
                        publisher=publisher,
                        anchor_time=context.simulation_time,
                        curve_spec=(
                            resolved_historical_configuration
                            .to_curve_spec()
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

                if (
                    generation_lifecycle
                    == GenerationLifecycle.CONTINUOUS
                ):
                    continuous_active_state = (
                        scenario.state_sequence[-2]
                    )

                    behaviour_generators = list(
                        zip(
                            scenario.behaviours,
                            generators,
                            strict=True,
                        )
                    )

                    prefix_generators = [
                        generator
                        for behaviour, generator
                        in behaviour_generators
                        if not (
                            behaviour.during_state
                            == continuous_active_state
                            and (
                                behaviour.continuous
                                or behaviour.source
                                == SourceDomain.EVIDENCE
                            )
                        )
                    ]

                    await runner.execute(
                        scenario=scenario,
                        context=context,
                        generators=prefix_generators,
                        publisher=publisher,
                        progress_observer=persist_progress,
                        event_interval_seconds=(
                            self._event_interval_seconds
                        ),
                        stop_at_state=(
                            continuous_active_state
                        ),
                    )

                    runtime_configuration = (
                        load_generator_runtime_configuration(
                            config_root=(
                                self._enterprise_root.parent
                            )
                        )
                    )

                    effective_frequency = (
                        resolve_source_frequency_configuration(
                            defaults=(
                                runtime_configuration.frequency
                            ),
                            override=scenario.frequency,
                        )
                    )

                    continuous_bindings = [
                        ContinuousSourceBinding(
                            behaviour=behaviour,
                            generator=generator,
                        )
                        for behaviour, generator
                        in behaviour_generators
                        if (
                            behaviour.continuous
                            and behaviour.during_state
                            == continuous_active_state
                        )
                    ]

                    continuous_publisher = (
                        _ContinuousProgressPublisher(
                            delegate=publisher,
                            state=context.scenario_state,
                            initial_event_count=len(
                                runner.event_history
                            ),
                            progress_observer=(
                                persist_progress
                            ),
                        )
                    )

                    scheduler = ContinuousSourceScheduler(
                        clock=clock,
                        runtime=(
                            runtime_configuration.runtime
                        ),
                        frequency=effective_frequency,
                        sleep_fn=asyncio.sleep,
                    )

                    await scheduler.run(
                        context=context,
                        bindings=continuous_bindings,
                        publisher=continuous_publisher,
                    )

                    raise RuntimeError(
                        "Continuous scheduler returned "
                        "unexpectedly."
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
                    or generation_lifecycle
                    == GenerationLifecycle.CONTINUOUS
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
                    or generation_lifecycle
                    == GenerationLifecycle.CONTINUOUS
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
            historical_configuration=(
                resolved_historical_configuration
            ),
            generation_lifecycle=(
                generation_lifecycle
            ),
            continuous_configuration=(
                resolved_continuous_configuration
            ),
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

    async def list_runs(
        self,
        *,
        status: RunStatus | None = None,
    ) -> tuple[RunRecord, ...]:
        if status is None:
            return await self._run_store.list_all()

        return await self._run_store.list_by_status(
            status
        )

    async def get_run_events(
        self,
        run_id: str,
    ) -> tuple[GeneratedEvent, ...]:
        record = await self.get_run(
            run_id
        )

        events = await self._store.get_run_events(
            record.run_id
        )

        return tuple(events)

    async def query_run_events(
        self,
        run_id: str,
        *,
        source_domain: SourceDomain | None = None,
        source_system: str | None = None,
        event_type: str | None = None,
        service: str | None = None,
        component: str | None = None,
        after_sequence_number: int | None = None,
        limit: int | None = None,
    ) -> tuple[GeneratedEvent, ...]:
        record = await self.get_run(
            run_id
        )

        events = await self._store.query_events(
            EventQuery(
                run_id=record.run_id,
                source_domain=source_domain,
                source_system=source_system,
                event_type=event_type,
                service=service,
                component=component,
                after_sequence_number=after_sequence_number,
                limit=limit,
            )
        )

        return tuple(events)

    async def count_run_events(
        self,
        run_id: str,
        *,
        source_domain: SourceDomain | None = None,
        source_system: str | None = None,
        event_type: str | None = None,
        service: str | None = None,
        component: str | None = None,
    ) -> int:
        record = await self.get_run(
            run_id
        )

        return await self._store.count_events(
            EventQuery(
                run_id=record.run_id,
                source_domain=source_domain,
                source_system=source_system,
                event_type=event_type,
                service=service,
                component=component,
            )
        )

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