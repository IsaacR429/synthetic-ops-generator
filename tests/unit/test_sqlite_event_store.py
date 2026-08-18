import sqlite3
from datetime import UTC, datetime, timedelta, timezone

import pytest

from synthetic_ops_generator.domain.enums import (
    Environment,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.events.serialization import (
    serialize_generated_event,
)
from synthetic_ops_generator.retention.query import EventQuery
from synthetic_ops_generator.retention.sqlite import SQLiteEventStore


def make_event(
    *,
    event_id: str = "EVT0000001",
    run_id: str = "RUN0000001",
    sequence_number: int = 1,
    event_time: datetime | None = None,
    source_domain: SourceDomain | None = None,
    source_system: str = "synthetic_test",
    event_type: str = "test.event",
    service: str = "payment_service",
    component: str | None = "payment_api",
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=event_id,
        event_type=event_type,
        event_time=event_time
        or datetime(
            2026,
            8,
            13,
            10,
            0,
            tzinfo=UTC,
        ),
        source_system=source_system,
        source_domain=source_domain,
        scenario_id="TEST-RETENTION-01",
        run_id=run_id,
        chg_id="CHG0000001",
        business_stream="payments",
        service=service,
        component=component,
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
async def test_query_events_requires_started_store(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    with pytest.raises(
        RuntimeError,
        match="SQLiteEventStore is not started",
    ):
        await store.query_events(
            EventQuery(
                run_id="RUN0000001",
            )
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
async def test_store_migrates_legacy_event_schema(
    tmp_path,
) -> None:
    database_path = tmp_path / "events.db"

    event = make_event()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE generated_events (
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
                serialize_generated_event(event),
            ),
        )

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    try:
        restored = await store.get_run_events(
            event.run_id
        )
    finally:
        await store.stop()

    with sqlite3.connect(database_path) as connection:
        columns = {
            str(row[1])
            for row in connection.execute(
                "PRAGMA table_info(generated_events)"
            ).fetchall()
        }

        projection = connection.execute(
            """
            SELECT
                source_domain,
                source_system,
                event_type,
                service,
                component
            FROM generated_events
            WHERE event_id = ?
            """,
            (event.event_id,),
        ).fetchone()

    assert restored == (event,)

    assert {
        "source_domain",
        "source_system",
        "event_type",
        "service",
        "component",
    } <= columns

    assert projection == (
        None,
        "synthetic_test",
        "test.event",
        "payment_service",
        "payment_api",
    )


@pytest.mark.asyncio
async def test_migrated_legacy_event_is_queryable_by_existing_metadata(
    tmp_path,
) -> None:
    database_path = tmp_path / "events.db"

    event = make_event()

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE generated_events (
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
                serialize_generated_event(event),
            ),
        )

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    try:
        by_event_type = await store.query_events(
            EventQuery(
                run_id=event.run_id,
                event_type="test.event",
            )
        )

        by_service = await store.query_events(
            EventQuery(
                run_id=event.run_id,
                service="payment_service",
            )
        )

        by_source_domain = await store.query_events(
            EventQuery(
                run_id=event.run_id,
                source_domain=SourceDomain.METRIC,
            )
        )
    finally:
        await store.stop()

    assert by_event_type == (
        event,
    )

    assert by_service == (
        event,
    )

    assert by_source_domain == ()


@pytest.mark.asyncio
async def test_store_persists_event_query_projection(
    tmp_path,
) -> None:
    database_path = tmp_path / "events.db"

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    event = make_event(
        source_domain=SourceDomain.METRIC,
    )

    try:
        await store.append(event)
    finally:
        await store.stop()

    with sqlite3.connect(database_path) as connection:
        projection = connection.execute(
            """
            SELECT
                source_domain,
                source_system,
                event_type,
                service,
                component
            FROM generated_events
            WHERE event_id = ?
            """,
            (event.event_id,),
        ).fetchone()

    assert projection == (
        "metric",
        "synthetic_test",
        "test.event",
        "payment_service",
        "payment_api",
    )


@pytest.mark.asyncio
async def test_query_events_is_scoped_to_run(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    first_run = make_event(
        event_id="EVT0000001",
        run_id="RUN0000001",
        sequence_number=1,
        source_domain=SourceDomain.METRIC,
    )

    second_run = make_event(
        event_id="EVT0000002",
        run_id="RUN0000002",
        sequence_number=1,
        source_domain=SourceDomain.METRIC,
    )

    try:
        await store.append(first_run)
        await store.append(second_run)

        restored = await store.query_events(
            EventQuery(
                run_id="RUN0000001",
            )
        )
    finally:
        await store.stop()

    assert restored == (
        first_run,
    )


@pytest.mark.asyncio
async def test_query_events_filters_by_source_domain(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    metric_event = make_event(
        event_id="EVT0000001",
        sequence_number=1,
        source_domain=SourceDomain.METRIC,
    )

    log_event = make_event(
        event_id="EVT0000002",
        sequence_number=2,
        source_domain=SourceDomain.LOG,
    )

    try:
        await store.append(metric_event)
        await store.append(log_event)

        restored = await store.query_events(
            EventQuery(
                run_id="RUN0000001",
                source_domain=SourceDomain.METRIC,
            )
        )
    finally:
        await store.stop()

    assert restored == (
        metric_event,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query_kwargs", "matching_kwargs"),
    [
        (
            {"source_system": "synthetic_metric"},
            {"source_system": "synthetic_metric"},
        ),
        (
            {"event_type": "metric.observed"},
            {"event_type": "metric.observed"},
        ),
        (
            {"service": "payment_service"},
            {"service": "payment_service"},
        ),
        (
            {"component": "payment_api"},
            {"component": "payment_api"},
        ),
    ],
)
async def test_query_events_filters_by_projection(
    tmp_path,
    query_kwargs,
    matching_kwargs,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    matching = make_event(
        event_id="EVT0000001",
        sequence_number=1,
        **matching_kwargs,
    )

    non_matching = make_event(
        event_id="EVT0000002",
        sequence_number=2,
        source_system="other_source",
        event_type="other.event",
        service="other_service",
        component="other_component",
    )

    try:
        await store.append(matching)
        await store.append(non_matching)

        restored = await store.query_events(
            EventQuery(
                run_id="RUN0000001",
                **query_kwargs,
            )
        )
    finally:
        await store.stop()

    assert restored == (
        matching,
    )


@pytest.mark.asyncio
async def test_query_events_combines_projection_filters(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    matching = make_event(
        event_id="EVT0000001",
        sequence_number=1,
        source_domain=SourceDomain.METRIC,
        source_system="synthetic_metric",
        event_type="metric.observed",
        service="payment_service",
        component="payment_api",
    )

    same_domain_wrong_type = make_event(
        event_id="EVT0000002",
        sequence_number=2,
        source_domain=SourceDomain.METRIC,
        source_system="synthetic_metric",
        event_type="metric.threshold_breached",
        service="payment_service",
        component="payment_api",
    )

    try:
        await store.append(matching)
        await store.append(same_domain_wrong_type)

        restored = await store.query_events(
            EventQuery(
                run_id="RUN0000001",
                source_domain=SourceDomain.METRIC,
                source_system="synthetic_metric",
                event_type="metric.observed",
                service="payment_service",
                component="payment_api",
            )
        )
    finally:
        await store.stop()

    assert restored == (
        matching,
    )


@pytest.mark.asyncio
async def test_query_events_rejects_empty_run_id(
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
            await store.query_events(
                EventQuery(
                    run_id="   ",
                )
            )
    finally:
        await store.stop()


@pytest.mark.asyncio
async def test_query_events_returns_events_in_sequence_order(
    tmp_path,
) -> None:
    store = SQLiteEventStore(
        database_path=tmp_path / "events.db"
    )

    await store.start()

    first = make_event(
        event_id="EVT0000001",
        sequence_number=1,
        source_domain=SourceDomain.METRIC,
    )

    second = make_event(
        event_id="EVT0000002",
        sequence_number=2,
        source_domain=SourceDomain.METRIC,
    )

    try:
        await store.append(second)
        await store.append(first)

        restored = await store.query_events(
            EventQuery(
                run_id="RUN0000001",
                source_domain=SourceDomain.METRIC,
            )
        )
    finally:
        await store.stop()

    assert restored == (
        first,
        second,
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


@pytest.mark.asyncio
async def test_store_creates_query_indexes(
    tmp_path,
) -> None:
    database_path = tmp_path / "events.db"

    store = SQLiteEventStore(
        database_path=database_path
    )

    await store.start()

    try:
        with sqlite3.connect(database_path) as connection:
            index_names = {
                str(row[1])
                for row in connection.execute(
                    "PRAGMA index_list(generated_events)"
                ).fetchall()
            }

            domain_columns = [
                str(row[2])
                for row in connection.execute(
                    """
                    PRAGMA index_info(
                        idx_generated_events_run_domain_sequence
                    )
                    """
                ).fetchall()
            ]

            type_columns = [
                str(row[2])
                for row in connection.execute(
                    """
                    PRAGMA index_info(
                        idx_generated_events_run_type_sequence
                    )
                    """
                ).fetchall()
            ]
    finally:
        await store.stop()

    assert (
        "idx_generated_events_run_sequence"
        not in index_names
    )

    assert (
        "idx_generated_events_event_time"
        in index_names
    )

    assert (
        "idx_generated_events_run_domain_sequence"
        in index_names
    )

    assert (
        "idx_generated_events_run_type_sequence"
        in index_names
    )

    assert domain_columns == [
        "run_id",
        "source_domain",
        "sequence_number",
    ]

    assert type_columns == [
        "run_id",
        "event_type",
        "sequence_number",
    ]
