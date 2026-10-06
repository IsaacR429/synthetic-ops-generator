import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.domain.enums import (
    SourceDomain,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    FAILED_DEPLOYMENT,
    REQUIRED_CHECK_FAILED,
)
from synthetic_ops_generator.scenarios.validator import (
    ScenarioValidationError,
    validate_scenario_against_enterprise,
)


def load_valid_objects():
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )

    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    return enterprise, scenario


def test_valid_bank_01_scenario() -> None:
    enterprise, scenario = load_valid_objects()

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_valid_bank_03_operational_degradation_scenario() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-03.yaml"
    )
    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_valid_bank_04_capacity_saturation_scenario() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )
    scenario = load_scenario(
        "config/scenarios/banking/BANK-04.yaml"
    )
    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )



def test_invalid_enterprise_reference_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.enterprise_id = "fake_bank"

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_invalid_service_reference_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.service_id = "fake_service"

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_invalid_component_reference_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.component_ids.append(
        "fake_component"
    )

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_component_from_wrong_service_raises() -> None:
    enterprise, scenario = load_valid_objects()

    scenario.target.component_ids = [
        "authentication_api"
    ]

    with pytest.raises(ScenarioValidationError):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_invalid_behaviour_profile_for_source_raises() -> None:
    enterprise, scenario = load_valid_objects()

    deployment_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.DEPLOYMENT
    )
    deployment_behaviour.profile_id = "healthy_baseline"

    with pytest.raises(
        ScenarioValidationError,
        match=(
            "Unsupported behaviour profile "
            "'healthy_baseline' for source 'deployment'"
        ),
    ):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_failed_deployment_profile_is_supported() -> None:
    enterprise, scenario = load_valid_objects()

    deployment_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.DEPLOYMENT
    )
    deployment_behaviour.profile_id = FAILED_DEPLOYMENT

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_required_check_failed_profile_is_supported() -> None:
    enterprise, scenario = load_valid_objects()

    infrastructure_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.INFRASTRUCTURE_TEST
    )
    infrastructure_behaviour.profile_id = REQUIRED_CHECK_FAILED

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_capacity_pressure_metric_profile_is_supported() -> None:
    enterprise, scenario = load_valid_objects()
    metric_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    )
    metric_behaviour.profile_id = "capacity_pressure"
    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_capacity_saturation_metric_profile_is_supported() -> None:
    enterprise, scenario = load_valid_objects()

    metric_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    )

    metric_behaviour.profile_id = "capacity_saturation"

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_capacity_recovery_metric_profile_is_supported() -> None:
    enterprise, scenario = load_valid_objects()

    metric_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    )

    metric_behaviour.profile_id = "capacity_recovery"

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )


def test_invalid_behaviour_execution_node_raises() -> None:
    enterprise, scenario = load_valid_objects()
    metric_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    )
    metric_behaviour.execution_node_id = (
        "missing_topology_node"
    )
    with pytest.raises(
        ScenarioValidationError,
        match="missing_topology_node",
    ):
        validate_scenario_against_enterprise(
            scenario,
            enterprise,
        )


def test_cross_service_behaviour_execution_node_is_valid() -> None:
    enterprise, scenario = load_valid_objects()
    metric_behaviour = next(
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.METRIC
    )
    metric_behaviour.execution_node_id = (
        "account_database"
    )
    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )
