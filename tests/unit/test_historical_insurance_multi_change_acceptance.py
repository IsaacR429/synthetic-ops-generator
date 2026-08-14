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


def build_scenarios():
    return {
        "INS-01": load_scenario(
            "config/scenarios/insurance/"
            "INS-01.yaml"
        ),
        "INS-02": load_scenario(
            "config/scenarios/insurance/"
            "INS-02.yaml"
        ),
    }


def build_insurance_history():
    ids = IdFactory()

    history = build_historical_change_history(
        ids=ids,
        enterprise_id="insurer_alpha",
        business_stream_id="claims",
        service_id="claims_service",
        start_time=START_TIME,
        entries=(
            HistoricalChangePlanEntry(
                scenario_id="INS-02",
                offset=timedelta(days=0),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="INS-02",
                offset=timedelta(days=7),
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="INS-01",
                offset=timedelta(days=14),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
            HistoricalChangePlanEntry(
                scenario_id="INS-01",
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
            "insurer_alpha"
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


def test_materializes_insurance_multi_change_history() -> None:
    history, materialized, _ = (
        build_insurance_history()
    )

    assert tuple(
        change.scenario_id
        for change in history.changes
    ) == (
        "INS-02",
        "INS-02",
        "INS-01",
        "INS-01",
    )

    assert tuple(
        len(child.events)
        for child in materialized.changes
    ) == (
        48,
        48,
        36,
        36,
    )

    assert len(
        materialized.events
    ) == 168


def test_insurance_history_preserves_child_run_and_service_identity() -> None:
    history, materialized, _ = (
        build_insurance_history()
    )

    for expected, child in zip(
        history.changes,
        materialized.changes,
        strict=True,
    ):
        assert child.change == expected

        assert (
            child.context.run_id
            == expected.run_id
        )

        assert (
            child.context.chg_id
            == expected.chg_id
        )

        assert (
            child.context.business_stream
            == "claims"
        )

        assert (
            child.context.service
            == "claims_service"
        )

        assert all(
            event.run_id
            == expected.run_id
            for event in child.events
        )

        assert all(
            event.chg_id
            == expected.chg_id
            for event in child.events
        )

        assert all(
            event.service
            == "claims_service"
            for event in child.events
        )


def test_insurance_history_exposes_improvement_facts() -> None:
    history, _, performance = (
        build_insurance_history()
    )

    assert tuple(
        change.outcome
        for change in history.changes
    ) == (
        HistoricalChangeOutcome.ROLLED_BACK,
        HistoricalChangeOutcome.ROLLED_BACK,
        HistoricalChangeOutcome.SUCCESSFUL,
        HistoricalChangeOutcome.SUCCESSFUL,
    )

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


def test_insurance_history_events_are_globally_chronological() -> None:
    _, materialized, _ = (
        build_insurance_history()
    )

    timestamps = tuple(
        event.event_time
        for event in materialized.events
    )

    assert timestamps == tuple(
        sorted(timestamps)
    )


def test_insurance_multi_change_history_is_reproducible() -> None:
    first = build_insurance_history()
    second = build_insurance_history()

    assert first == second
