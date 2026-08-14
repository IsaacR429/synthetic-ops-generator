from datetime import UTC, datetime, timedelta

import pytest

from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeCase,
    HistoricalChangeHistory,
    HistoricalChangeOutcome,
    HistoricalChangePlanEntry,
    build_historical_change_history,
)

BASE_TIME = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)


def make_change(
    ordinal: int,
    *,
    scenario_id: str = "BANK-02",
    run_id: str | None = None,
    chg_id: str | None = None,
    change_time: datetime | None = None,
    outcome: HistoricalChangeOutcome = (
        HistoricalChangeOutcome.SUCCESSFUL
    ),
) -> HistoricalChangeCase:
    return HistoricalChangeCase(
        ordinal=ordinal,
        scenario_id=scenario_id,
        run_id=run_id or f"RUN000000{ordinal}",
        chg_id=chg_id or f"CHG000000{ordinal}",
        change_time=(
            change_time
            or (
                BASE_TIME
                + timedelta(hours=ordinal)
            )
        ),
        outcome=outcome,
    )


def test_valid_historical_change_history_constructs() -> None:
    history = HistoricalChangeHistory(
        history_id="HST0000001",
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        changes=(
            make_change(
                1,
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
            make_change(
                2,
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
            make_change(
                3,
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
        ),
    )

    assert history.history_id == "HST0000001"
    assert history.enterprise_id == "bank_alpha"
    assert history.business_stream_id == "payments"
    assert history.service_id == "payment_service"
    assert len(history.changes) == 3
    assert history.changes[0].ordinal == 1
    assert (
        history.changes[1].outcome
        == HistoricalChangeOutcome.ROLLED_BACK
    )


def test_historical_change_history_requires_at_least_two_changes() -> None:
    with pytest.raises(
        ValueError,
        match="requires at least two Changes",
    ):
        HistoricalChangeHistory(
            history_id="HST0000001",
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            changes=(make_change(1),),
        )


def test_historical_change_history_enforces_ordinal_sequence() -> None:
    with pytest.raises(
        ValueError,
        match="must be contiguous and begin at 1",
    ):
        HistoricalChangeHistory(
            history_id="HST0000001",
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            changes=(
                make_change(1),
                make_change(3),
            ),
        )


def test_historical_change_history_rejects_duplicate_run_ids() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate Run IDs",
    ):
        HistoricalChangeHistory(
            history_id="HST0000001",
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            changes=(
                make_change(
                    1,
                    run_id="RUN0000001",
                ),
                make_change(
                    2,
                    run_id="RUN0000001",
                ),
            ),
        )


def test_historical_change_history_rejects_duplicate_change_ids() -> None:
    with pytest.raises(
        ValueError,
        match="duplicate CHG IDs",
    ):
        HistoricalChangeHistory(
            history_id="HST0000001",
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            changes=(
                make_change(
                    1,
                    chg_id="CHG0000001",
                ),
                make_change(
                    2,
                    chg_id="CHG0000001",
                ),
            ),
        )


def test_historical_change_history_requires_strict_chronology() -> None:
    same_time = BASE_TIME

    with pytest.raises(
        ValueError,
        match="strictly chronological",
    ):
        HistoricalChangeHistory(
            history_id="HST0000001",
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            changes=(
                make_change(
                    1,
                    change_time=same_time,
                ),
                make_change(
                    2,
                    change_time=same_time,
                ),
            ),
        )


def test_historical_change_requires_timezone_aware_time() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        HistoricalChangeCase(
            ordinal=1,
            scenario_id="BANK-02",
            run_id="RUN0000001",
            chg_id="CHG0000001",
            change_time=datetime(  # noqa: DTZ001
                2026,
                1,
                1,
                10,
                0,
            ),
            outcome=(
                HistoricalChangeOutcome.ROLLED_BACK
            ),
        )


def test_build_history_allocates_parent_and_change_identities() -> None:
    ids = IdFactory()

    history = build_historical_change_history(
        ids=ids,
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        start_time=BASE_TIME,
        entries=(
            HistoricalChangePlanEntry(
                scenario_id="BANK-01",
                offset=timedelta(days=0),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="BANK-02",
                offset=timedelta(days=7),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="BANK-02",
                offset=timedelta(days=14),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
        ),
    )

    assert history.history_id == (
        "HST0000001"
    )

    assert [
        change.run_id
        for change in history.changes
    ] == [
        "RUN0000001",
        "RUN0000002",
        "RUN0000003",
    ]

    assert [
        change.chg_id
        for change in history.changes
    ] == [
        "CHG0000001",
        "CHG0000002",
        "CHG0000003",
    ]


def test_build_history_applies_change_offsets() -> None:
    history = build_historical_change_history(
        ids=IdFactory(),
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        start_time=BASE_TIME,
        entries=(
            HistoricalChangePlanEntry(
                scenario_id="BANK-01",
                offset=timedelta(days=0),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="BANK-02",
                offset=timedelta(days=5),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="BANK-01",
                offset=timedelta(days=13),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
        ),
    )

    assert [
        change.change_time
        for change in history.changes
    ] == [
        BASE_TIME,
        BASE_TIME + timedelta(days=5),
        BASE_TIME + timedelta(days=13),
    ]


def test_build_history_preserves_declared_outcomes() -> None:
    history = build_historical_change_history(
        ids=IdFactory(),
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        start_time=BASE_TIME,
        entries=(
            HistoricalChangePlanEntry(
                scenario_id="BANK-01",
                offset=timedelta(days=0),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="BANK-02",
                offset=timedelta(days=7),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
        ),
    )

    assert [
        change.outcome
        for change in history.changes
    ] == [
        HistoricalChangeOutcome.SUCCESSFUL,
        HistoricalChangeOutcome.ROLLED_BACK,
    ]


def test_build_history_rejects_non_increasing_offsets() -> None:
    with pytest.raises(
        ValueError,
        match="offsets",
    ):
        build_historical_change_history(
            ids=IdFactory(),
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            start_time=BASE_TIME,
            entries=(
                HistoricalChangePlanEntry(
                    scenario_id="BANK-01",
                    offset=timedelta(days=5),
                    outcome=(
                        HistoricalChangeOutcome.SUCCESSFUL
                    ),
                ),
                HistoricalChangePlanEntry(
                    scenario_id="BANK-02",
                    offset=timedelta(days=5),
                    outcome=(
                        HistoricalChangeOutcome.ROLLED_BACK
                    ),
                ),
            ),
        )


def test_build_history_requires_aware_start_time() -> None:
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        build_historical_change_history(
            ids=IdFactory(),
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            start_time=datetime(  # noqa: DTZ001
                2026,
                1,
                1,
                10,
                0,
            ),
            entries=(
                HistoricalChangePlanEntry(
                    scenario_id="BANK-01",
                    offset=timedelta(days=0),
                    outcome=(
                        HistoricalChangeOutcome.SUCCESSFUL
                    ),
                ),
                HistoricalChangePlanEntry(
                    scenario_id="BANK-02",
                    offset=timedelta(days=1),
                    outcome=(
                        HistoricalChangeOutcome.ROLLED_BACK
                    ),
                ),
            ),
        )
