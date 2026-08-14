from pathlib import Path

import pytest

from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.replay.service import (
    ReplayService,
)
from synthetic_ops_generator.retention.sqlite import (
    SQLiteEventStore,
)
from tests.unit.test_historical_retention_integration import (
    build_bank_02_historical_events,
)


@pytest.mark.asyncio
async def test_persisted_historical_run_replays_exactly(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    database_path = (
        tmp_path
        / "historical-replay.db"
    )

    initial_store = SQLiteEventStore(
        database_path=database_path
    )

    await initial_store.start()

    try:
        for event in events:
            await initial_store.append(
                event
            )
    finally:
        await initial_store.stop()

    replay_store = SQLiteEventStore(
        database_path=database_path
    )

    destination = InMemoryPublisher()

    replay_service = ReplayService(
        store=replay_store,
        publisher=destination,
    )

    await replay_store.start()

    try:
        replayed_count = (
            await replay_service.replay_run(
                context.run_id
            )
        )
    finally:
        await replay_store.stop()

    assert replayed_count == 48

    assert destination.events == list(
        events
    )


@pytest.mark.asyncio
async def test_historical_replay_preserves_original_event_times(
    tmp_path: Path,
) -> None:
    dataset, context, events = (
        build_bank_02_historical_events()
    )

    database_path = (
        tmp_path
        / "historical-times.db"
    )

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    try:
        for event in events:
            await store.append(event)
    finally:
        await store.stop()

    replay_store = SQLiteEventStore(
        database_path=database_path
    )

    destination = InMemoryPublisher()

    service = ReplayService(
        store=replay_store,
        publisher=destination,
    )

    await replay_store.start()

    try:
        await service.replay_run(
            context.run_id
        )
    finally:
        await replay_store.stop()

    assert tuple(
        event.event_time
        for event in destination.events
    ) == tuple(
        event.event_time
        for event in events
    )

    assert (
        destination.events[0].event_time
        < dataset.change_boundary_time
    )

    assert (
        destination.events[-1].event_time
        > dataset.rollback_boundary_time
    )


@pytest.mark.asyncio
async def test_historical_replay_preserves_canonical_sequence(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "historical-sequence.db"
        )
    )

    await store.start()

    try:
        for event in reversed(events):
            await store.append(event)

        destination = InMemoryPublisher()

        service = ReplayService(
            store=store,
            publisher=destination,
        )

        replayed_count = (
            await service.replay_run(
                context.run_id
            )
        )
    finally:
        await store.stop()

    assert replayed_count == 48

    assert tuple(
        event.sequence_number
        for event in destination.events
    ) == tuple(
        range(1, 49)
    )

    assert destination.events == list(
        events
    )


@pytest.mark.asyncio
async def test_historical_context_survives_replay(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "historical-context-replay.db"
        )
    )

    await store.start()

    try:
        for event in events:
            await store.append(event)

        destination = InMemoryPublisher()

        service = ReplayService(
            store=store,
            publisher=destination,
        )

        await service.replay_run(
            context.run_id
        )
    finally:
        await store.stop()

    assert all(
        "historical"
        in event.data["metric"]
        for event in destination.events
    )

    for original, replayed in zip(
        events,
        destination.events,
        strict=True,
    ):
        assert (
            replayed
            .data["metric"]["historical"]
            == original
            .data["metric"]["historical"]
        )


@pytest.mark.asyncio
async def test_historical_run_can_be_replayed_repeatedly(
    tmp_path: Path,
) -> None:
    _, context, events = (
        build_bank_02_historical_events()
    )

    store = SQLiteEventStore(
        database_path=(
            tmp_path
            / "historical-repeat.db"
        )
    )

    await store.start()

    try:
        for event in events:
            await store.append(event)

        first_destination = (
            InMemoryPublisher()
        )

        first_service = ReplayService(
            store=store,
            publisher=first_destination,
        )

        first_count = (
            await first_service.replay_run(
                context.run_id
            )
        )

        second_destination = (
            InMemoryPublisher()
        )

        second_service = ReplayService(
            store=store,
            publisher=second_destination,
        )

        second_count = (
            await second_service.replay_run(
                context.run_id
            )
        )
    finally:
        await store.stop()

    assert first_count == 48
    assert second_count == 48

    assert (
        first_destination.events
        == second_destination.events
        == list(events)
    )
