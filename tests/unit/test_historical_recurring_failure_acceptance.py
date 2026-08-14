from datetime import UTC, datetime, timedelta
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
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

CONFIG_ROOT = Path("config")

START_TIME = datetime(
    2026,
    8,
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


def build_recurring_failure_history():
    ids = IdFactory()

    history = build_historical_change_history(
        ids=ids,
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        start_time=START_TIME,
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
            HistoricalChangePlanEntry(
                scenario_id="BANK-02",
                offset=timedelta(days=21),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
        ),
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    scenarios = {
        "BANK-01": load_scenario(
            "config/scenarios/banking/"
            "BANK-01.yaml"
        ),
        "BANK-02": load_scenario(
            "config/scenarios/banking/"
            "BANK-02.yaml"
        ),
    }

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

    return history, materialized


def test_recurring_failure_history_contains_multiple_rollback_runs() -> None:
    history, _ = (
        build_recurring_failure_history()
    )

    rolled_back = tuple(
        change
        for change in history.changes
        if (
            change.outcome
            == HistoricalChangeOutcome.ROLLED_BACK
        )
    )

    assert len(rolled_back) == 3

    assert len(
        {
            change.run_id
            for change in rolled_back
        }
    ) == 3

    assert len(
        {
            change.chg_id
            for change in rolled_back
        }
    ) == 3


def test_recurring_failures_target_same_payment_service() -> None:
    _, materialized = (
        build_recurring_failure_history()
    )

    failed_children = tuple(
        child
        for child in materialized.changes
        if (
            child.change.outcome
            == HistoricalChangeOutcome.ROLLED_BACK
        )
    )

    assert len(failed_children) == 3

    assert {
        child.context.service
        for child in failed_children
    } == {
        "payment_service"
    }

    assert all(
        event.service
        == "payment_service"
        for child in failed_children
        for event in child.events
    )


def test_recurring_failure_history_repeats_bank_02_failure_scenario() -> None:
    history, _ = (
        build_recurring_failure_history()
    )

    assert tuple(
        change.scenario_id
        for change in history.changes
    ) == (
        "BANK-01",
        "BANK-02",
        "BANK-02",
        "BANK-02",
    )


def test_each_recurring_failure_has_complete_incident_history() -> None:
    _, materialized = (
        build_recurring_failure_history()
    )

    failed_children = tuple(
        child
        for child in materialized.changes
        if (
            child.change.outcome
            == HistoricalChangeOutcome.ROLLED_BACK
        )
    )

    assert tuple(
        len(child.events)
        for child in failed_children
    ) == (
        48,
        48,
        48,
    )

    assert all(
        {
            event.data["metric"][
                "metric_definition_id"
            ]
            for event in child.events
        }
        == {
            "request_latency",
            "error_rate",
            "availability",
        }
        for child in failed_children
    )


def test_recurring_failure_history_is_chronological() -> None:
    history, materialized = (
        build_recurring_failure_history()
    )

    change_times = tuple(
        change.change_time
        for change in history.changes
    )

    assert change_times == tuple(
        sorted(change_times)
    )

    event_times = tuple(
        event.event_time
        for event in materialized.events
    )

    assert event_times == tuple(
        sorted(event_times)
    )


def test_recurring_failure_history_has_expected_event_volume() -> None:
    _, materialized = (
        build_recurring_failure_history()
    )

    assert len(
        materialized.events
    ) == 180


def test_recurring_failure_history_is_reproducible() -> None:
    first_history, first = (
        build_recurring_failure_history()
    )

    second_history, second = (
        build_recurring_failure_history()
    )

    assert first_history == second_history
    assert first == second
    assert first.events == second.events
