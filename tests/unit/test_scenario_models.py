import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioMetricSelection,
    SourceDomain,
)


def test_expected_result_scenario_id_must_match() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    data = scenario.model_dump()

    data["expected_result"]["scenario_id"] = "BANK-99"

    with pytest.raises(ValidationError):
        type(scenario).model_validate(data)


def test_behaviour_state_must_exist_in_sequence() -> None:
    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    data = scenario.model_dump()

    data["behaviours"][0]["during_state"] = "failure"

    with pytest.raises(ValidationError):
        type(scenario).model_validate(data)


def test_metric_behaviour_can_select_metric_ids() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.METRIC,
        during_state=OperationalState.WARNING,
        profile_id="operational_warning",
        selection=ScenarioMetricSelection(
            metric_ids=[
                "request_latency",
                "error_rate",
            ],
        ),
    )
    assert behaviour.selection is not None
    assert behaviour.selection.metric_ids == [
        "request_latency",
        "error_rate",
    ]


def test_non_metric_behaviour_rejects_metric_selection() -> None:
    with pytest.raises(
        ValidationError,
        match="Metric selection is only valid for Metric behaviour",
    ):
        ScenarioBehaviour(
            source=SourceDomain.LOG,
            during_state=OperationalState.WARNING,
            profile_id="operational_degradation",
            selection=ScenarioMetricSelection(
                metric_ids=[
                    "request_latency",
                ],
            ),
        )


def test_metric_selection_rejects_empty_metric_ids() -> None:
    with pytest.raises(ValidationError):
        ScenarioMetricSelection(
            metric_ids=[],
        )


def test_metric_selection_rejects_blank_metric_id() -> None:
    with pytest.raises(ValidationError):
        ScenarioMetricSelection(
            metric_ids=[
                "",
            ],
        )


def test_metric_selection_rejects_whitespace_only_metric_id() -> None:
    with pytest.raises(ValidationError):
        ScenarioMetricSelection(
            metric_ids=[
                "   ",
            ],
        )


def test_metric_selection_rejects_duplicate_metric_ids() -> None:
    with pytest.raises(
        ValidationError,
        match="Metric selection cannot contain duplicate IDs",
    ):
        ScenarioMetricSelection(
            metric_ids=[
                "request_latency",
                "request_latency",
            ],
        )


def test_behaviour_can_declare_execution_node_id() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.DEGRADED,
        profile_id="degradation_error_logs",
        execution_node_id="account_database",
    )
    assert (
        behaviour.execution_node_id
        == "account_database"
    )


def test_behaviour_rejects_blank_execution_node_id() -> None:
    with pytest.raises(ValidationError):
        ScenarioBehaviour(
            source=SourceDomain.LOG,
            during_state=OperationalState.DEGRADED,
            profile_id="degradation_error_logs",
            execution_node_id="   ",
        )


def test_behaviour_execution_node_defaults_to_none() -> None:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.DEGRADED,
        profile_id="degradation_error_logs",
    )
    assert behaviour.execution_node_id is None
