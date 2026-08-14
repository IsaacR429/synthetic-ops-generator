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


def build_four_change_history(
    *,
    ids: IdFactory,
):
    return build_historical_change_history(
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
                scenario_id="BANK-01",
                offset=timedelta(days=21),
                outcome=(
                    HistoricalChangeOutcome.SUCCESSFUL
                ),
            ),
        ),
    )


def test_materializes_complete_multi_change_history() -> None:
    ids = IdFactory()

    history = build_four_change_history(
        ids=ids
    )

    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "bank_alpha"
        )
    )

    materialized = (
        materialize_historical_change_history(
            history=history,
            scenarios=build_scenarios(),
            enterprise=enterprise,
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    assert (
        materialized.history
        == history
    )

    assert len(
        materialized.changes
    ) == 4

    assert tuple(
        change.change
        for change in materialized.changes
    ) == history.changes


def test_multi_change_history_dispatches_each_outcome() -> None:
    ids = IdFactory()

    materialized = (
        materialize_historical_change_history(
            history=build_four_change_history(
                ids=ids
            ),
            scenarios=build_scenarios(),
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    assert tuple(
        len(change.events)
        for change in materialized.changes
    ) == (
        36,
        48,
        48,
        36,
    )

    assert len(
        materialized.events
    ) == 168


def test_multi_change_history_preserves_all_child_identities() -> None:
    ids = IdFactory()

    history = build_four_change_history(
        ids=ids
    )

    materialized = (
        materialize_historical_change_history(
            history=history,
            scenarios=build_scenarios(),
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    for expected, actual in zip(
        history.changes,
        materialized.changes,
        strict=True,
    ):
        assert (
            actual.context.run_id
            == expected.run_id
        )

        assert (
            actual.context.chg_id
            == expected.chg_id
        )

        assert all(
            event.run_id
            == expected.run_id
            for event in actual.events
        )

        assert all(
            event.chg_id
            == expected.chg_id
            for event in actual.events
        )


def test_multi_change_history_derives_child_seeds() -> None:
    ids = IdFactory()

    materialized = (
        materialize_historical_change_history(
            history=build_four_change_history(
                ids=ids
            ),
            scenarios=build_scenarios(),
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    assert tuple(
        change.context.random_seed
        for change in materialized.changes
    ) == (
        42,
        43,
        44,
        45,
    )


def test_materialized_history_events_are_globally_chronological() -> None:
    ids = IdFactory()

    materialized = (
        materialize_historical_change_history(
            history=build_four_change_history(
                ids=ids
            ),
            scenarios=build_scenarios(),
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=ids,
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


def test_multi_change_history_rejects_missing_scenario_definition() -> None:
    ids = IdFactory()

    history = build_four_change_history(
        ids=ids
    )

    with pytest.raises(
        ValueError,
        match="BANK-02",
    ):
        materialize_historical_change_history(
            history=history,
            scenarios={
                "BANK-01": (
                    build_scenarios()[
                        "BANK-01"
                    ]
                )
            },
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )


def test_multi_change_history_rejects_enterprise_mismatch() -> None:
    ids = IdFactory()

    history = build_four_change_history(
        ids=ids
    )

    wrong_enterprise = (
        load_enterprise_configuration(
            "config/enterprises/"
            "insurer_alpha"
        )
    )

    with pytest.raises(
        ValueError,
        match="Enterprise",
    ):
        materialize_historical_change_history(
            history=history,
            scenarios=build_scenarios(),
            enterprise=wrong_enterprise,
            config_root=CONFIG_ROOT,
            ids=ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )


def test_parent_materializer_does_not_allocate_operational_ids() -> None:
    ids = IdFactory()

    history = build_four_change_history(
        ids=ids
    )

    materialize_historical_change_history(
        history=history,
        scenarios=build_scenarios(),
        enterprise=(
            load_enterprise_configuration(
                "config/enterprises/"
                "bank_alpha"
            )
        ),
        config_root=CONFIG_ROOT,
        ids=ids,
        random_seed=42,
        incident_curve_spec=(
            INCIDENT_CURVE
        ),
    )

    assert ids.run_id() == "RUN0000005"
    assert ids.change_id() == "CHG0000005"


def test_multi_change_history_is_deterministic_for_same_seed() -> None:
    first_ids = IdFactory()
    second_ids = IdFactory()

    first = (
        materialize_historical_change_history(
            history=build_four_change_history(
                ids=first_ids
            ),
            scenarios=build_scenarios(),
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=first_ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    second = (
        materialize_historical_change_history(
            history=build_four_change_history(
                ids=second_ids
            ),
            scenarios=build_scenarios(),
            enterprise=(
                load_enterprise_configuration(
                    "config/enterprises/"
                    "bank_alpha"
                )
            ),
            config_root=CONFIG_ROOT,
            ids=second_ids,
            random_seed=42,
            incident_curve_spec=(
                INCIDENT_CURVE
            ),
        )
    )

    assert first == second
    assert first.events == second.events
