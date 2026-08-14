from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeOutcome,
    HistoricalChangePlanEntry,
    build_historical_change_history,
)
from synthetic_ops_generator.history.change_history_materializer import (
    materialize_historical_change_history,
)
from synthetic_ops_generator.history.change_performance import (
    build_historical_change_performance_history,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

CONFIG_ROOT = Path("config")

START_TIME = datetime(
    2026,
    7,
    1,
    10,
    0,
    tzinfo=UTC,
)

INCIDENT_CURVE = PerturbationCurveSpec(
    degradation_samples=4,
    plateau_samples=2,
    recovery_samples=4,
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


def build_improving_history():
    ids = IdFactory()

    history = build_historical_change_history(
        ids=ids,
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

    scenarios = build_scenarios()

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    materialized = (
        materialize_historical_change_history(
            history=history,
            scenarios=scenarios,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    performance = (
        build_historical_change_performance_history(
            history=history,
            scenarios=scenarios,
            validation_durations_seconds={
                1: 900,
                2: 600,
                3: 300,
                4: 180,
            },
        )
    )

    return (
        history,
        materialized,
        performance,
    )


def test_improvement_history_moves_from_failure_to_success() -> None:
    history, _, _ = build_improving_history()

    assert tuple(
        change.outcome
        for change in history.changes
    ) == (
        HistoricalChangeOutcome.ROLLED_BACK,
        HistoricalChangeOutcome.ROLLED_BACK,
        HistoricalChangeOutcome.SUCCESSFUL,
        HistoricalChangeOutcome.SUCCESSFUL,
    )


def test_later_history_has_more_successful_changes() -> None:
    history, _, _ = build_improving_history()

    earlier = history.changes[:2]
    later = history.changes[2:]

    earlier_successes = sum(
        change.outcome
        == HistoricalChangeOutcome.SUCCESSFUL
        for change in earlier
    )

    later_successes = sum(
        change.outcome
        == HistoricalChangeOutcome.SUCCESSFUL
        for change in later
    )

    assert earlier_successes == 0
    assert later_successes == 2
    assert later_successes > earlier_successes


def test_later_history_has_fewer_failed_changes() -> None:
    history, _, _ = build_improving_history()

    earlier = history.changes[:2]
    later = history.changes[2:]

    earlier_failures = sum(
        change.outcome
        == HistoricalChangeOutcome.ROLLED_BACK
        for change in earlier
    )

    later_failures = sum(
        change.outcome
        == HistoricalChangeOutcome.ROLLED_BACK
        for change in later
    )

    assert earlier_failures == 2
    assert later_failures == 0
    assert later_failures < earlier_failures


def test_later_history_has_fewer_change_incidents() -> None:
    _, _, performance = (
        build_improving_history()
    )

    earlier = performance.changes[:2]
    later = performance.changes[2:]

    earlier_incidents = sum(
        item.incident_created
        for item in earlier
    )

    later_incidents = sum(
        item.incident_created
        for item in later
    )

    assert earlier_incidents == 2
    assert later_incidents == 0
    assert later_incidents < earlier_incidents


def test_validation_duration_improves_over_time() -> None:
    _, _, performance = (
        build_improving_history()
    )

    durations = tuple(
        item.validation_duration_seconds
        for item in performance.changes
    )

    assert durations == (
        900,
        600,
        300,
        180,
    )

    assert all(
        current < previous
        for previous, current in pairwise(
            durations
        )
    )


def test_later_validation_period_is_faster_than_earlier_period() -> None:
    _, _, performance = (
        build_improving_history()
    )

    durations = tuple(
        item.validation_duration_seconds
        for item in performance.changes
    )

    earlier_average = (
        sum(durations[:2]) / 2
    )

    later_average = (
        sum(durations[2:]) / 2
    )

    assert earlier_average == 750
    assert later_average == 240
    assert later_average < earlier_average


def test_improvement_history_retains_operational_telemetry() -> None:
    _, materialized, _ = (
        build_improving_history()
    )

    assert tuple(
        len(change.events)
        for change in materialized.changes
    ) == (
        48,
        48,
        36,
        36,
    )

    assert len(
        materialized.events
    ) == 168


def test_improvement_performance_preserves_run_identity() -> None:
    history, materialized, performance = (
        build_improving_history()
    )

    for expected, child, facts in zip(
        history.changes,
        materialized.changes,
        performance.changes,
        strict=True,
    ):
        assert child.change == expected
        assert facts.change == expected

        assert (
            child.context.run_id
            == expected.run_id
        )

        assert (
            child.context.chg_id
            == expected.chg_id
        )


def test_improvement_history_is_reproducible() -> None:
    first = build_improving_history()
    second = build_improving_history()

    assert first == second
