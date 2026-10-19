from pathlib import Path

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.checks.catalogue import (
    DEFAULT_INFRASTRUCTURE_CHECKS,
)
from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioCheckSelection,
    SourceDomain,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"


def _selected_ids(
    generator: InfrastructureTestGenerator,
) -> tuple[str, ...]:
    return tuple(
        spec.definition.check_definition_id
        for spec in generator._checks
    )


def _bank_01():
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-01.yaml"
    )

    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )

    return scenario, enterprise


def _scenario_with_infrastructure_selection(
    check_definition_ids: list[str],
):
    scenario, enterprise = _bank_01()

    infrastructure_index = next(
        index
        for index, behaviour in enumerate(
            scenario.behaviours
        )
        if (
            behaviour.source
            == SourceDomain.INFRASTRUCTURE_TEST
        )
    )

    original = scenario.behaviours[
        infrastructure_index
    ]

    payload = original.model_dump(
        mode="python"
    )
    payload["check_selection"] = (
        ScenarioCheckSelection(
            check_definition_ids=(
                check_definition_ids
            )
        )
    )

    selected = ScenarioBehaviour.model_validate(
        payload
    )

    behaviours = list(
        scenario.behaviours
    )
    behaviours[infrastructure_index] = selected

    scenario = scenario.model_copy(
        update={
            "behaviours": behaviours,
        }
    )

    return (
        scenario,
        enterprise,
        infrastructure_index,
    )


def test_infrastructure_behaviour_accepts_check_selection() -> None:
    selection = ScenarioCheckSelection(
        check_definition_ids=[
            "infrastructure.dns_resolution",
            "infrastructure.certificate_validation",
        ]
    )

    behaviour = ScenarioBehaviour(
        behaviour_id="fixture_infrastructure_selection",
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.NORMAL,
        profile_id="all_required_checks_pass",
        check_selection=selection,
    )

    assert behaviour.check_selection == selection
    assert behaviour.selection is None


def test_check_selection_is_rejected_for_metric_behaviour() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Check selection is only valid for "
            "infrastructure-test behaviour"
        ),
    ):
        ScenarioBehaviour(
            behaviour_id="fixture_invalid_check_selection",
            source=SourceDomain.METRIC,
            during_state=OperationalState.NORMAL,
            profile_id="normal",
            check_selection=ScenarioCheckSelection(
                check_definition_ids=[
                    "infrastructure.dns_resolution",
                ]
            ),
        )


def test_factory_preserves_selected_infrastructure_check_order() -> None:
    selected_ids = [
        "infrastructure.dependency_connectivity",
        "infrastructure.dns_resolution",
        "infrastructure.certificate_validation",
    ]

    (
        scenario,
        enterprise,
        infrastructure_index,
    ) = _scenario_with_infrastructure_selection(
        selected_ids
    )

    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    generator = generators[
        infrastructure_index
    ]

    assert isinstance(
        generator,
        InfrastructureTestGenerator,
    )

    assert _selected_ids(generator) == tuple(
        selected_ids
    )


def test_factory_rejects_unknown_selected_infrastructure_check() -> None:
    scenario, enterprise, _ = (
        _scenario_with_infrastructure_selection(
            [
                "infrastructure.dns_resolution",
                "infrastructure.does_not_exist",
            ]
        )
    )

    with pytest.raises(
        ValueError,
        match=(
            "Unknown Infrastructure Check Definition: "
            "infrastructure.does_not_exist"
        ),
    ):
        GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build(
            scenario=scenario,
            enterprise=enterprise,
            ids=IdFactory(),
            random_source=SimulationRandom(42),
            event_history=[],
        )


def test_factory_keeps_default_infrastructure_checks_without_selection() -> None:
    scenario, enterprise = _bank_01()

    infrastructure_index = next(
        index
        for index, behaviour in enumerate(
            scenario.behaviours
        )
        if (
            behaviour.source
            == SourceDomain.INFRASTRUCTURE_TEST
        )
    )

    generators = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build(
        scenario=scenario,
        enterprise=enterprise,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    generator = generators[
        infrastructure_index
    ]

    assert isinstance(
        generator,
        InfrastructureTestGenerator,
    )

    assert _selected_ids(generator) == tuple(
        spec.definition.check_definition_id
        for spec in DEFAULT_INFRASTRUCTURE_CHECKS
    )
