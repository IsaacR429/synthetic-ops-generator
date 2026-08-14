from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeCase,
    HistoricalChangeOutcome,
    HistoricalChangePlanEntry,
    build_historical_change_history,
)
from synthetic_ops_generator.history.change_materializer import (
    materialize_historical_change,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

CONFIG_ROOT = Path("config")

CHANGE_TIME = datetime(
    2026,
    8,
    14,
    10,
    0,
    tzinfo=UTC,
)

INCIDENT_CURVE = PerturbationCurveSpec(
    degradation_samples=4,
    plateau_samples=2,
    recovery_samples=4,
)


def build_change(
    *,
    scenario_id: str,
    outcome: HistoricalChangeOutcome,
    run_id: str,
    chg_id: str,
) -> HistoricalChangeCase:
    return HistoricalChangeCase(
        ordinal=1,
        scenario_id=scenario_id,
        run_id=run_id,
        chg_id=chg_id,
        change_time=CHANGE_TIME,
        outcome=outcome,
    )


def test_materializes_successful_change_into_healthy_events() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-01.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    change = build_change(
        scenario_id="BANK-01",
        outcome=(
            HistoricalChangeOutcome.SUCCESSFUL
        ),
        run_id="RUN0000042",
        chg_id="CHG0000042",
    )

    materialized = (
        materialize_historical_change(
            change=change,
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=IdFactory(),
            random_seed=42,
        )
    )

    assert materialized.change == change

    assert (
        materialized.context.run_id
        == "RUN0000042"
    )

    assert (
        materialized.context.chg_id
        == "CHG0000042"
    )

    assert len(
        materialized.events
    ) == 36

    assert all(
        event.scenario_id == "BANK-01"
        for event in materialized.events
    )

    assert all(
        event.run_id == "RUN0000042"
        for event in materialized.events
    )

    assert all(
        event.chg_id == "CHG0000042"
        for event in materialized.events
    )


def test_materializes_rolled_back_change_into_incident_events() -> None:
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

    change = build_change(
        scenario_id="BANK-02",
        outcome=(
            HistoricalChangeOutcome.ROLLED_BACK
        ),
        run_id="RUN0000043",
        chg_id="CHG0000043",
    )

    materialized = (
        materialize_historical_change(
            change=change,
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=IdFactory(),
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    assert len(
        materialized.events
    ) == 48

    assert all(
        event.scenario_id == "BANK-02"
        for event in materialized.events
    )

    assert all(
        event.run_id == "RUN0000043"
        for event in materialized.events
    )

    assert all(
        event.chg_id == "CHG0000043"
        for event in materialized.events
    )


def test_rolled_back_change_requires_incident_curve() -> None:
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

    change = build_change(
        scenario_id="BANK-02",
        outcome=(
            HistoricalChangeOutcome.ROLLED_BACK
        ),
        run_id="RUN0000043",
        chg_id="CHG0000043",
    )

    with pytest.raises(
        ValueError,
        match="incident curve",
    ):
        materialize_historical_change(
            change=change,
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=IdFactory(),
            random_seed=42,
        )


def test_successful_change_does_not_require_incident_curve() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-01.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    materialized = (
        materialize_historical_change(
            change=build_change(
                scenario_id="BANK-01",
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
                run_id="RUN0000042",
                chg_id="CHG0000042",
            ),
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=IdFactory(),
            random_seed=42,
        )
    )

    assert len(
        materialized.events
    ) == 36


def test_materializer_does_not_allocate_new_run_or_change_ids() -> None:
    ids = IdFactory()

    history = build_historical_change_history(
        ids=ids,
        enterprise_id="bank_alpha",
        business_stream_id="payments",
        service_id="payment_service",
        start_time=CHANGE_TIME,
        entries=(
            HistoricalChangePlanEntry(
                scenario_id="BANK-01",
                offset=timedelta(0),
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

    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-01.yaml"
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    first_change = history.changes[0]

    materialized = (
        materialize_historical_change(
            change=first_change,
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
        )
    )

    assert (
        materialized.context.run_id
        == first_change.run_id
    )

    assert (
        materialized.context.chg_id
        == first_change.chg_id
    )

    # The history already allocated RUN1/CHG1
    # and RUN2/CHG2. Materialization must not
    # allocate another operational identity.
    assert ids.run_id() == "RUN0000003"
    assert ids.change_id() == "CHG0000003"


def test_materialized_change_events_are_chronological() -> None:
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

    materialized = (
        materialize_historical_change(
            change=build_change(
                scenario_id="BANK-02",
                outcome=(
                    HistoricalChangeOutcome.ROLLED_BACK
                ),
                run_id="RUN0000043",
                chg_id="CHG0000043",
            ),
            scenario=scenario,
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=IdFactory(),
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    timestamps = tuple(
        event.event_time
        for event in materialized.events
    )

    assert timestamps == tuple(
        sorted(timestamps)
    )
