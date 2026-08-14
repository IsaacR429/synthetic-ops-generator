from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.history.change_context import (
    build_historical_change_context,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeCase,
    HistoricalChangeOutcome,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)

BASE_TIME = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)


def build_change(
    scenario_id: str = "BANK-01",
    run_id: str = "RUN0000001",
    chg_id: str = "CHG0000001",
) -> HistoricalChangeCase:
    return HistoricalChangeCase(
        ordinal=1,
        scenario_id=scenario_id,
        run_id=run_id,
        chg_id=chg_id,
        change_time=BASE_TIME,
        outcome=HistoricalChangeOutcome.SUCCESSFUL,
    )


def test_builds_historical_change_context_from_preallocated_identities() -> None:
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

    change = build_change()

    context = build_historical_change_context(
        change=change,
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    assert context.scenario_id == "BANK-01"
    assert context.run_id == "RUN0000001"
    assert context.chg_id == "CHG0000001"
    assert context.business_stream == "payments"
    assert context.service == "payment_service"
    assert context.component == "payment_api"
    assert context.environment == "production"
    assert context.simulation_time == BASE_TIME
    assert context.random_seed == 42
    assert context.sequence_number == 0
    assert context.risk == scenario.risk
    assert (
        context.scenario_state
        == scenario.state_sequence[0]
    )


def test_historical_context_preserves_random_seed() -> None:
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

    context = build_historical_change_context(
        change=build_change(),
        scenario=scenario,
        enterprise=enterprise,
        random_seed=1234,
    )

    assert context.random_seed == 1234


def test_historical_context_rejects_scenario_mismatch() -> None:
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
        scenario_id="BANK-02"
    )

    with pytest.raises(
        ValueError,
        match="scenario_id",
    ):
        build_historical_change_context(
            change=change,
            scenario=scenario,
            enterprise=enterprise,
            random_seed=42,
        )


def test_historical_context_rejects_enterprise_mismatch() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/"
        "BANK-01.yaml"
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
        build_historical_change_context(
            change=build_change(),
            scenario=scenario,
            enterprise=wrong_enterprise,
            random_seed=42,
        )
