from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.history.change_history import (
    HistoricalChangeCase,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
)


def build_historical_change_context(
    *,
    change: HistoricalChangeCase,
    scenario: ScenarioDefinition,
    enterprise: Enterprise,
    random_seed: int,
) -> ScenarioContext:
    """
    Build the ScenarioContext for one Change
    inside a HistoricalChangeHistory.

    HistoricalChangeCase owns its Run ID and
    CHG ID. No new operational identity is
    allocated here.
    """
    if (
        change.scenario_id
        != scenario.scenario_id
    ):
        raise ValueError(
            "Historical Change scenario_id "
            "does not match Scenario definition."
        )

    if (
        scenario.target.enterprise_id
        != enterprise.enterprise_id
    ):
        raise ValueError(
            "Historical Change Scenario target "
            "does not match supplied Enterprise."
        )

    component = (
        scenario.target.component_ids[0]
        if scenario.target.component_ids
        else None
    )

    return ScenarioContext(
        scenario_id=scenario.scenario_id,
        run_id=change.run_id,
        chg_id=change.chg_id,
        business_stream=(
            scenario.target.business_stream_id
        ),
        service=scenario.target.service_id,
        component=component,
        environment=scenario.target.environment,
        risk=scenario.risk,
        scenario_state=(
            scenario.state_sequence[0]
        ),
        simulation_time=change.change_time,
        random_seed=random_seed,
    )
