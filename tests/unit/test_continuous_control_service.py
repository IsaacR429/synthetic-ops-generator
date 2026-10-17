import asyncio
from pathlib import Path

import pytest

from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)
from synthetic_ops_generator.control.configuration import (
    ContinuousExecutionConfiguration,
    ContinuousStopMode,
    GenerationLifecycle,
)
from synthetic_ops_generator.control.models import (
    RunExecutionMode,
    RunStatus,
)
from synthetic_ops_generator.control.service import (
    ControlService,
    RunExecutionModeNotSupportedError,
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
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)
from synthetic_ops_generator.scenarios.continuous import (
    ContinuousSourceBinding,
    ContinuousSourceScheduler,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioResilienceTransition,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


@pytest.mark.asyncio
async def test_control_service_starts_and_stops_continuous_run(
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

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
            generation_lifecycle=(
                GenerationLifecycle.CONTINUOUS
            ),
        )

        assert started.status == RunStatus.RUNNING

        running_records = await service.list_runs(
            status=RunStatus.RUNNING
        )

        assert len(running_records) == 1
        assert (
            running_records[0].run_id
            == started.run_id
        )

        # Give the continuous run time to execute bounded prefix and generate continuous events
        await asyncio.sleep(0.5)

        live_record = await service.get_run(
            started.run_id
        )
        assert live_record is not None
        if live_record.status == RunStatus.FAILED:
            print("LIVE RECORD FAILED WITH ERROR:", live_record.error_message)
        assert live_record.status == RunStatus.RUNNING
        assert (
            live_record.generation_lifecycle
            == GenerationLifecycle.CONTINUOUS
        )

        stopped = await service.stop_run(
            started.run_id
        )
        assert stopped.status == RunStatus.STOPPED
        assert stopped.event_count > 0

        running_records_after_stop = (
            await service.list_runs(
                status=RunStatus.RUNNING
            )
        )

        assert running_records_after_stop == ()

        all_records_after_stop = (
            await service.list_runs()
        )

        stopped_record = next(
            (
                record
                for record in all_records_after_stop
                if record.run_id == started.run_id
            ),
            None,
        )

        assert stopped_record is not None
        assert stopped_record.status == RunStatus.STOPPED

        final_record = await service.get_run(
            started.run_id
        )
        assert final_record is not None
        assert final_record.status == RunStatus.STOPPED
        assert (
            final_record.current_state
            == OperationalState.OBSERVING
        )
        assert final_record.completed_at is not None

        events = await store.get_run_events(
            started.run_id
        )
        assert len(events) == stopped.event_count

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_continuous_generation_rejects_historical_mode(
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

        with pytest.raises(
            RunExecutionModeNotSupportedError,
            match=(
                "Continuous lifecycle is not supported "
                "for historical execution"
            ),
        ):
            await service.start_run(
                scenario_id="BANK-02",
                random_seed=42,
                execution_mode=(
                    RunExecutionMode.HISTORICAL
                ),
                generation_lifecycle=(
                    GenerationLifecycle.CONTINUOUS
                ),
            )


    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_continuous_generation_rejects_duration_stop_mode(
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

        with pytest.raises(
            RunExecutionModeNotSupportedError,
            match=(
                "Duration-based continuous "
                "execution is not supported yet"
            ),
        ):
            await service.start_run(
                scenario_id="BANK-01",
                random_seed=42,
                generation_lifecycle=(
                    GenerationLifecycle.CONTINUOUS
                ),
                continuous_configuration=(
                    ContinuousExecutionConfiguration(
                        stop_mode=(
                            ContinuousStopMode.DURATION
                        ),
                        duration_seconds=60,
                    )
                ),
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_scenario_without_continuous_active_behaviour_is_rejected(
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

        with pytest.raises(
            RunExecutionModeNotSupportedError,
            match=(
                "does not define continuous "
                "behaviour in its final active state"
            ),
        ):
            await service.start_run(
                scenario_id="INS-01",
                random_seed=42,
                generation_lifecycle=(
                    GenerationLifecycle.CONTINUOUS
                ),
            )

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_continuous_control_service_propagates_execution_target(
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

    base_catalogue = ScenarioCatalogue(
        CONFIG_ROOT / "scenarios"
    )
    original_scenario = base_catalogue.get_scenario("BANK-01")
    assert original_scenario is not None

    updated_behaviours = []
    for b in original_scenario.behaviours:
        if b.continuous and b.source == SourceDomain.LOG:
            updated_behaviours.append(
                b.model_copy(
                    update={"execution_node_id": "payment_database"}
                )
            )
        else:
            updated_behaviours.append(b)

    targeted_scenario = original_scenario.model_copy(
        update={"behaviours": updated_behaviours}
    )

    class MockCatalogue(ScenarioCatalogue):
        def __init__(self) -> None:
            pass

        def get_scenario(self, scenario_id: str):
            if scenario_id == "BANK-01":
                return targeted_scenario
            return None

    try:
        service = ControlService(
            catalogue=MockCatalogue(),
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

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
            generation_lifecycle=(
                GenerationLifecycle.CONTINUOUS
            ),
        )

        assert started.status == RunStatus.RUNNING

        await asyncio.sleep(0.5)

        stopped = await service.stop_run(
            started.run_id
        )
        assert stopped.status == RunStatus.STOPPED

        events = await store.get_run_events(
            started.run_id
        )
        log_events = [
            e
            for e in events
            if e.source_domain == SourceDomain.LOG
        ]
        assert len(log_events) > 0

        targeted_logs = [
            e
            for e in log_events
            if e.component == "payment_database"
        ]
        assert len(targeted_logs) > 0
        for log_event in targeted_logs:
            assert log_event.service == "payment_service"
            assert log_event.component == "payment_database"

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()



@pytest.mark.asyncio
async def test_continuous_control_service_keeps_resilience_transition_bounded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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

    base_catalogue = ScenarioCatalogue(
        CONFIG_ROOT / "scenarios"
    )
    original_scenario = base_catalogue.get_scenario(
        "BANK-01"
    )
    assert original_scenario is not None

    # Give the existing final-active continuous LOG a concrete
    # secondary Service Instance execution identity.
    updated_behaviours = []

    for behaviour in original_scenario.behaviours:
        if (
            behaviour.continuous
            and behaviour.source == SourceDomain.LOG
        ):
            updated_behaviours.append(
                behaviour.model_copy(
                    update={
                        "execution_node_id": (
                            "payment_api_secondary"
                        )
                    }
                )
            )
        else:
            updated_behaviours.append(
                behaviour
            )

    # Add one bounded factual resilience transition.
    resilience_behaviour = ScenarioBehaviour(
        behaviour_id="fixture_test_continuous_control_service_01",
        source=SourceDomain.RESILIENCE,
        during_state=(
            original_scenario.state_sequence[1]
        ),
        profile_id="failover_initiated",
        continuous=False,
        execution_node_id="payment_api_primary",
        resilience_transition=(
            ScenarioResilienceTransition(
                to_execution_node_id=(
                    "payment_api_secondary"
                )
            )
        ),
    )

    mixed_scenario = original_scenario.model_copy(
        update={
            "behaviours": [
                resilience_behaviour,
                *updated_behaviours,
            ],
        }
    )

    class MockCatalogue(ScenarioCatalogue):
        def __init__(self) -> None:
            pass

        def get_scenario(self, scenario_id: str):
            if scenario_id == "BANK-01":
                return mixed_scenario
            return None

    scheduler_entered = asyncio.Event()

    captured_bindings: list[
        ContinuousSourceBinding
    ] = []

    async def capture_scheduler_handoff(
        self,
        *,
        context,
        bindings,
        publisher,
    ) -> None:
        del self, context, publisher

        captured_bindings.extend(bindings)

        scheduler_entered.set()

        # Remain inside the continuous lifecycle until stop_run()
        # cancels the managed background task.
        await asyncio.Event().wait()

    monkeypatch.setattr(
        ContinuousSourceScheduler,
        "run",
        capture_scheduler_handoff,
    )

    try:
        service = ControlService(
            catalogue=MockCatalogue(),
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

        started = await service.start_run(
            scenario_id="BANK-01",
            random_seed=42,
            generation_lifecycle=(
                GenerationLifecycle.CONTINUOUS
            ),
        )

        assert started.status == RunStatus.RUNNING

        await asyncio.wait_for(
            scheduler_entered.wait(),
            timeout=2.0,
        )

        # At this exact point the bounded prefix has completed,
        # while the continuous scheduler has emitted nothing.
        prefix_events = await store.get_run_events(
            started.run_id
        )

        resilience_events = [
            event
            for event in prefix_events
            if event.source_domain
            == SourceDomain.RESILIENCE
        ]

        assert len(resilience_events) == 1

        resilience_event = resilience_events[0]

        assert (
            resilience_event.site_id
            == "bank_primary"
        )
        assert (
            resilience_event.service_instance_id
            == "payment_api_primary"
        )

        observation = resilience_event.data[
            "resilience_observation"
        ]

        assert (
            observation["from_site_id"]
            == "bank_primary"
        )
        assert (
            observation[
                "from_service_instance_id"
            ]
            == "payment_api_primary"
        )
        assert (
            observation["to_site_id"]
            == "bank_secondary"
        )
        assert (
            observation[
                "to_service_instance_id"
            ]
            == "payment_api_secondary"
        )

        # Final-active continuous evidence must not have been
        # emitted during the bounded prefix.
        assert not any(
            event.source_domain == SourceDomain.LOG
            and event.service_instance_id
            == "payment_api_secondary"
            for event in prefix_events
        )

        # Resilience observations must never cross the continuous
        # scheduler boundary.
        assert all(
            binding.behaviour.source
            != SourceDomain.RESILIENCE
            for binding in captured_bindings
        )

        secondary_log_bindings = [
            binding
            for binding in captured_bindings
            if (
                binding.behaviour.source
                == SourceDomain.LOG
                and binding.execution_target
                is not None
                and (
                    binding.execution_target
                    .service_instance_id
                    == "payment_api_secondary"
                )
            )
        ]

        assert len(
            secondary_log_bindings
        ) > 0

        for binding in secondary_log_bindings:
            assert (
                binding.execution_target
                is not None
            )
            assert (
                binding.execution_target.site_id
                == "bank_secondary"
            )
            assert (
                binding.execution_target.service
                == "payment_service"
            )
            assert (
                binding.execution_target.component
                == "payment_api"
            )

        stopped = await service.stop_run(
            started.run_id
        )

        assert stopped.status == RunStatus.STOPPED

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()


@pytest.mark.asyncio
async def test_bank_06_managed_runtime_preserves_failover_evidence(
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

        started = await service.start_run(
            scenario_id="BANK-06",
            random_seed=42,
            generation_lifecycle=(
                GenerationLifecycle.CONTINUOUS
            ),
        )

        assert started.status == RunStatus.RUNNING

        resilience_events = []
        secondary_continuous_events = []

        for _ in range(30):
            await asyncio.sleep(0.1)

            live_record = await service.get_run(
                started.run_id
            )

            assert live_record is not None

            assert live_record.status != RunStatus.FAILED, (
                live_record.error_message
            )

            events = await store.get_run_events(
                started.run_id
            )

            resilience_events = sorted(
                (
                    event
                    for event in events
                    if (
                        event.source_domain
                        == SourceDomain.RESILIENCE
                    )
                ),
                key=lambda event: event.sequence_number,
            )

            secondary_continuous_events = [
                event
                for event in events
                if (
                    event.source_domain
                    in {
                        SourceDomain.METRIC,
                        SourceDomain.LOG,
                    }
                    and event.site_id == "bank_secondary"
                    and (
                        event.service_instance_id
                        == "payment_api_secondary"
                    )
                )
            ]

            secondary_sources = {
                event.source_domain
                for event in secondary_continuous_events
            }

            if (
                len(resilience_events) == 5
                and secondary_sources
                == {
                    SourceDomain.METRIC,
                    SourceDomain.LOG,
                }
            ):
                break
        else:
            pytest.fail(
                "BANK-06 did not produce the expected "
                "bounded resilience evidence and secondary "
                "continuous telemetry."
            )

        assert [
            event.data["behaviour_profile_id"]
            for event in resilience_events
        ] == [
            "failover_initiated",
            "traffic_switch_started",
            "traffic_switch_completed",
            "instance_activated",
            "instance_serving",
        ]

        for event in resilience_events[:3]:
            assert event.site_id == "bank_primary"
            assert (
                event.service_instance_id
                == "payment_api_primary"
            )

            observation = event.data[
                "resilience_observation"
            ]

            assert (
                observation["from_site_id"]
                == "bank_primary"
            )
            assert (
                observation[
                    "from_service_instance_id"
                ]
                == "payment_api_primary"
            )
            assert (
                observation["to_site_id"]
                == "bank_secondary"
            )
            assert (
                observation[
                    "to_service_instance_id"
                ]
                == "payment_api_secondary"
            )

        for event in resilience_events[3:]:
            assert event.site_id == "bank_secondary"
            assert (
                event.service_instance_id
                == "payment_api_secondary"
            )

            observation = event.data[
                "resilience_observation"
            ]

            assert observation["from_site_id"] is None
            assert (
                observation[
                    "from_service_instance_id"
                ]
                is None
            )
            assert (
                observation["to_site_id"]
                == "bank_secondary"
            )
            assert (
                observation[
                    "to_service_instance_id"
                ]
                == "payment_api_secondary"
            )

        assert {
            event.source_domain
            for event in secondary_continuous_events
        } == {
            SourceDomain.METRIC,
            SourceDomain.LOG,
        }

        for event in secondary_continuous_events:
            assert event.site_id == "bank_secondary"
            assert (
                event.service_instance_id
                == "payment_api_secondary"
            )

        stopped = await service.stop_run(
            started.run_id
        )

        assert stopped.status == RunStatus.STOPPED

        final_events = await store.get_run_events(
            started.run_id
        )

        final_resilience_events = [
            event
            for event in final_events
            if (
                event.source_domain
                == SourceDomain.RESILIENCE
            )
        ]

        # Resilience facts are bounded even though the run
        # itself continues to produce operational telemetry.
        assert len(final_resilience_events) == 5

    finally:
        await active_run_manager.shutdown()
        await run_store.stop()
        await store.stop()
