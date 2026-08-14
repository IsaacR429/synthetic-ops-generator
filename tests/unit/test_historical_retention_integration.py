from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.history.event_adapter import (
    build_historical_metric_events,
)
from synthetic_ops_generator.history.incident_dataset import (
    build_historical_incident_dataset,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.history.scenario_runtime import (
    build_historical_scenario_runtime,
)
from synthetic_ops_generator.publishers.retention import (
    RetentionPublisher,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.runner import (
    ScenarioRunner,
)

CONFIG_ROOT = Path("config")


def build_bank_02_historical_events():
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-02.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    runtime = (
        build_historical_scenario_runtime(
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
        )
    )

    anchor_time = datetime(
        2026,
        8,
        14,
        10,
        0,
        tzinfo=UTC,
    )

    dataset = (
        build_historical_incident_dataset(
            runtime=runtime,
            anchor_time=anchor_time,
            curve_spec=(
                PerturbationCurveSpec(
                    degradation_samples=4,
                    plateau_samples=2,
                    recovery_samples=4,
                )
            ),
            random_source=(
                SimulationRandom(
                    seed=42
                )
            ),
        )
    )

    ids = IdFactory()

    runner = ScenarioRunner(
        ids=ids,
        clock=ManualSimulationClock(
            anchor_time
        ),
    )

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    events = build_historical_metric_events(
        dataset=dataset,
        runtime=runtime,
        context=context,
        ids=ids,
    )

    return dataset, context, events


@pytest.mark.asyncio
async def test_historical_events_persist_and_restore_exactly(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    database_path = (
        tmp_path
        / "historical-events.db"
    )

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    publisher = RetentionPublisher(
        store=store
    )

    try:
        for event in events:
            await publisher.publish(
                event
            )
    finally:
        await store.stop()

    reopened_store = SQLiteEventStore(
        database_path=database_path
    )

    await reopened_store.start()

    try:
        restored = (
            await reopened_store
            .get_run_events(
                context.run_id
            )
        )
    finally:
        await reopened_store.stop()

    assert restored == events

    assert len(restored) == 48

    assert tuple(
        event.sequence_number
        for event in restored
    ) == tuple(
        range(1, 49)
    )


@pytest.mark.asyncio
async def test_historical_context_survives_sqlite_round_trip(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    database_path = (
        tmp_path
        / "historical-context.db"
    )

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    publisher = RetentionPublisher(
        store=store
    )

    try:
        for event in events:
            await publisher.publish(
                event
            )
    finally:
        await store.stop()

    reopened_store = SQLiteEventStore(
        database_path=database_path
    )

    await reopened_store.start()

    try:
        restored = (
            await reopened_store
            .get_run_events(
                context.run_id
            )
        )
    finally:
        await reopened_store.stop()

    assert all(
        "historical"
        in event.data["metric"]
        for event in restored
    )

    historical = (
        restored[0]
        .data["metric"]["historical"]
    )

    assert set(historical) == {
        "counterfactual_value",
        "perturbation_strength",
        "perturbation_phase",
    }


@pytest.mark.asyncio
async def test_retained_historical_events_preserve_timeline(
    tmp_path: Path,
) -> None:
    dataset, context, events = (
        build_bank_02_historical_events()
    )

    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "historical-timeline.db"
        )
    )

    await store.start()

    publisher = RetentionPublisher(
        store=store
    )

    try:
        for event in events:
            await publisher.publish(
                event
            )

        restored = (
            await store.get_run_events(
                context.run_id
            )
        )
    finally:
        await store.stop()

    timestamps = tuple(
        event.event_time
        for event in restored
    )

    assert all(
        current <= following
        for current, following
        in pairwise(timestamps)
    )

    assert (
        restored[0].event_time
        < dataset.change_boundary_time
    )

    assert (
        restored[-1].event_time
        > dataset.rollback_boundary_time
    )


@pytest.mark.asyncio
async def test_historical_events_restore_in_canonical_sequence_order(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "historical-order.db"
        )
    )

    await store.start()

    publisher = RetentionPublisher(
        store=store
    )

    try:
        for event in reversed(
            events
        ):
            await publisher.publish(
                event
            )

        restored = (
            await store.get_run_events(
                context.run_id
            )
        )
    finally:
        await store.stop()

    assert restored == events

    assert tuple(
        event.sequence_number
        for event in restored
    ) == tuple(
        range(1, 49)
    )
