from datetime import UTC, datetime, timedelta

import pytest

from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeOutcome,
    HistoricalChangePlanEntry,
    build_historical_change_history,
)
from synthetic_ops_generator.history.change_performance import (
    HistoricalChangePerformance,
    build_historical_change_performance,
    build_historical_change_performance_history,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

START_TIME = datetime(
    2026,
    7,
    1,
    10,
    0,
    tzinfo=UTC,
)


def build_history():
    return build_historical_change_history(
        ids=IdFactory(),
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        start_time=START_TIME,
        entries=(
            HistoricalChangePlanEntry(
                scenario_id="BANK-02",
                offset=timedelta(days=0),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
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
                scenario_id="BANK-01",
                offset=timedelta(days=14),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="BANK-01",
                offset=timedelta(days=21),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
        ),
    )


def build_scenarios():
    return {
        "BANK-01": load_scenario(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        "BANK-02": load_scenario(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
    }


def test_bank_02_performance_records_incident_created() -> None:
    history = build_history()

    performance = (
        build_historical_change_performance(
            change=history.changes[0],
            scenario=build_scenarios()[
                "BANK-02"
            ],
            validation_duration_seconds=900,
        )
    )

    assert performance.change == (
        history.changes[0]
    )

    assert performance.incident_created is True

    assert (
        performance.validation_duration_seconds
        == 900
    )


def test_bank_01_performance_records_no_incident() -> None:
    history = build_history()

    performance = (
        build_historical_change_performance(
            change=history.changes[2],
            scenario=build_scenarios()[
                "BANK-01"
            ],
            validation_duration_seconds=300,
        )
    )

    assert performance.incident_created is False

    assert (
        performance.validation_duration_seconds
        == 300
    )


@pytest.mark.parametrize(
    "duration",
    (0, -1),
)
def test_historical_performance_rejects_invalid_duration(
    duration: int,
) -> None:
    history = build_history()

    with pytest.raises(
        ValueError,
        match="duration",
    ):
        HistoricalChangePerformance(
            change=history.changes[0],
            incident_created=True,
            validation_duration_seconds=duration,
        )


def test_builds_performance_facts_for_complete_history() -> None:
    history = build_history()

    performance = (
        build_historical_change_performance_history(
            history=history,
            scenarios=build_scenarios(),
            validation_durations_seconds={
                1: 900,
                2: 600,
                3: 300,
                4: 180,
            },
        )
    )

    assert tuple(
        item.change
        for item in performance.changes
    ) == history.changes

    assert tuple(
        item.incident_created
        for item in performance.changes
    ) == (
        True,
        True,
        False,
        False,
    )

    assert tuple(
        item.validation_duration_seconds
        for item in performance.changes
    ) == (
        900,
        600,
        300,
        180,
    )


def test_performance_history_requires_duration_for_every_change() -> None:
    history = build_history()

    with pytest.raises(
        ValueError,
        match="ordinal 4",
    ):
        build_historical_change_performance_history(
            history=history,
            scenarios=build_scenarios(),
            validation_durations_seconds={
                1: 900,
                2: 600,
                3: 300,
            },
        )


def test_performance_history_rejects_unknown_duration_ordinal() -> None:
    history = build_history()

    with pytest.raises(
        ValueError,
        match="unknown",
    ):
        build_historical_change_performance_history(
            history=history,
            scenarios=build_scenarios(),
            validation_durations_seconds={
                1: 900,
                2: 600,
                3: 300,
                4: 180,
                5: 120,
            },
        )


def test_performance_rejects_scenario_mismatch() -> None:
    history = build_history()

    with pytest.raises(
        ValueError,
        match="scenario_id",
    ):
        build_historical_change_performance(
            change=history.changes[0],
            scenario=build_scenarios()[
                "BANK-01"
            ],
            validation_duration_seconds=900,
        )
