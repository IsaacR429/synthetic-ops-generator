import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from synthetic_ops_generator.domain.enums import Environment
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.retention.sqlite import SQLiteEventStore


def make_event(
    *,
    event_id: str = "EVT0000001",
    run_id: str = "RUN0000001",
    sequence_number: int = 1,
    event_time: datetime | None = None,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type="test.event",
        event_time=event_time
        or datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        source_system="synthetic_test",
        scenario_id="TEST-RETENTION-01",
        run_id=run_id,
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
        data={
            "message": "retention test",
        },
    )


@pytest.mark.asyncio
async def test_store_requires_start_before_append(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    with pytest.raises(
        RuntimeError,
        match="SQLiteEventStore is not started",
    ):
        await store.append(
            make_event()
        )


@pytest.mark.asyncio
async def test_store_persists_and_restores_event(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    event = make_event()

    try:
        await store.append(event)

        restored = await store.get_run_events(
            event.run_id
        )
    finally:
        await store.stop()

    assert restored == (event,)


@pytest.mark.asyncio
async def test_store_returns_run_events_in_sequence_order(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
    )

    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
    )

    try:
        await store.append(second)
        await store.append(first)

        restored = await store.get_run_events(
            "RUN0000001"
        )
    finally:
        await store.stop()

    assert restored == (
        first,
        second,
    )


@pytest.mark.asyncio
async def test_store_filters_events_by_run(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    first_run = make_event(
        event_id="EVT0000001",
        run_id="RUN0000001",
    )

    second_run = make_event(
        event_id="EVT0000002",
        run_id="RUN0000002",
    )

    try:
        await store.append(first_run)
        await store.append(second_run)

        restored = await store.get_run_events(
            "RUN0000001"
        )
    finally:
        await store.stop()

    assert restored == (
        first_run,
    )


@pytest.mark.asyncio
async def test_store_persists_across_store_instances(
    tmp_path,
) -> None:
    database_path = tmp_path / "events.db"

    first_store = SQLiteEventStore(
        database_path=database_path
    )

    await first_store.start()

    event = make_event()

    await first_store.append(event)
    await first_store.stop()

    second_store = SQLiteEventStore(
        database_path=database_path
    )

    await second_store.start()

    try:
        restored = await second_store.get_run_events(
            event.run_id
        )
    finally:
        await second_store.stop()

    assert restored == (
        event,
    )


@pytest.mark.asyncio
async def test_store_rejects_duplicate_event_id(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    event = make_event()

    try:
        await store.append(event)

        with pytest.raises(sqlite3.IntegrityError):
            await store.append(event)
    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_store_rejects_empty_run_id(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    try:
        with pytest.raises(
            ValueError,
            match="Run ID is required",
        ):
            await store.get_run_events("   ")
    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_store_deletes_events_before_cutoff(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    cutoff = datetime(
        2026,
        8,
        13,
        10,
        0,
        tzinfo=UTC,
    )

    old_event = make_event(
        event_id="EVT0000001",
        sequence_number=1,
        event_time=datetime(
            2026,
            8,
            13,
            9,
            59,
            tzinfo=UTC,
        ),
    )

    cutoff_event = make_event(
        event_id="EVT0000002",
        sequence_number=2,
        event_time=cutoff,
    )

    future_event = make_event(
        event_id="EVT0000003",
        sequence_number=3,
        event_time=datetime(
            2026,
            8,
            13,
            10,
            1,
            tzinfo=UTC,
        ),
    )

    try:
        await store.append(old_event)
        await store.append(cutoff_event)
        await store.append(future_event)

        deleted = await store.delete_before(
            cutoff
        )

        remaining = await store.get_run_events(
            "RUN0000001"
        )
    finally:
        await store.stop()

    assert deleted == 1

    assert remaining == (
        cutoff_event,
        future_event,
    )


@pytest.mark.asyncio
async def test_store_returns_deleted_event_count(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
        event_time=datetime(
            2026,
            8,
            12,
            10,
            0,
            tzinfo=UTC,
        ),
    )

    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
        event_time=datetime(
            2026,
            8,
            12,
            11,
            0,
            tzinfo=UTC,
        ),
    )

    try:
        await store.append(first)
        await store.append(second)

        deleted = await store.delete_before(
            datetime(
                2026,
                8,
                13,
                10,
                0,
                tzinfo=UTC,
            )
        )
    finally:
        await store.stop()

    assert deleted == 2


@pytest.mark.asyncio
async def test_store_rejects_naive_retention_cutoff(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    try:
        with pytest.raises(
            ValueError,
            match="timezone-aware",
        ):
            await store.delete_before(
                datetime(  # noqa: DTZ001
                    2026,
                    8,
                    13,
                    10,
                    0,
                )
            )
    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_store_normalizes_retention_cutoff_to_utc(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    event = make_event(
        event_time=datetime(
            2026,
            8,
            13,
            9,
            0,
            tzinfo=UTC,
        )
    )

    sri_lanka_timezone = timezone(
        timedelta(
            hours=5,
            minutes=30,
        )
    )

    cutoff = datetime(
        2026,
        8,
        13,
        15,
        0,
        tzinfo=sri_lanka_timezone,
    )

    try:
        await store.append(event)

        deleted = await store.delete_before(
            cutoff
        )
    finally:
        await store.stop()

    assert deleted == 1
