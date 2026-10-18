from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from synthetic_ops_generator.checks.catalogue import (
    APPLICATION_FUNCTIONAL_VALIDATION,
    APPLICATION_POST_DEPLOYMENT_SMOKE,
    APPLICATION_TRANSACTION_PROCESSING,
    DEFAULT_APPLICATION_CHECKS,
    DEFAULT_INFRASTRUCTURE_CHECKS,
    INFRASTRUCTURE_CONNECTIVITY,
    INFRASTRUCTURE_DEPENDENCY_CONNECTIVITY,
    INFRASTRUCTURE_SERVICE_HEALTH,
)
from synthetic_ops_generator.checks.models import (
    CheckExecutionSpec,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.domain.enums import (
    AssetClass,
    Environment,
    OperationalState,
    RiskLevel,
    ServiceClass,
)
from synthetic_ops_generator.domain.operational_test import (
    TestCategory as Category,
)
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestGenerator,
)
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


def _context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="INS-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=datetime(
            2026,
            10,
            17,
            12,
            0,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


def _application_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id="fixture_p1b_application",
        source=SourceDomain.APPLICATION_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="all_mandatory_tests_pass",
    )


def _infrastructure_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id="fixture_p1b_infrastructure",
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="all_required_checks_pass",
    )


async def _collect(generator, context):
    events = []

    async for event in generator.generate(context):
        events.append(event)

    return events


def test_application_catalogue_has_stable_definition_identities() -> None:
    assert [
        spec.definition.check_definition_id
        for spec in DEFAULT_APPLICATION_CHECKS
    ] == [
        "application.functional_validation",
        "application.transaction_processing",
        "application.post_deployment_smoke",
    ]

    assert tuple(
        spec.definition
        for spec in DEFAULT_APPLICATION_CHECKS
    ) == (
        APPLICATION_FUNCTIONAL_VALIDATION,
        APPLICATION_TRANSACTION_PROCESSING,
        APPLICATION_POST_DEPLOYMENT_SMOKE,
    )

    assert all(
        spec.definition.category
        == Category.APPLICATION
        for spec in DEFAULT_APPLICATION_CHECKS
    )

    assert all(
        ServiceClass.BUSINESS_APPLICATION
        in spec.definition.applicability.service_classes
        for spec in DEFAULT_APPLICATION_CHECKS
    )


def test_infrastructure_catalogue_has_stable_definition_identities() -> None:
    assert [
        spec.definition.check_definition_id
        for spec in DEFAULT_INFRASTRUCTURE_CHECKS
    ] == [
        "infrastructure.connectivity",
        "infrastructure.service_health",
        "infrastructure.dependency_connectivity",
    ]

    assert tuple(
        spec.definition
        for spec in DEFAULT_INFRASTRUCTURE_CHECKS
    ) == (
        INFRASTRUCTURE_CONNECTIVITY,
        INFRASTRUCTURE_SERVICE_HEALTH,
        INFRASTRUCTURE_DEPENDENCY_CONNECTIVITY,
    )

    assert all(
        spec.definition.category
        == Category.INFRASTRUCTURE
        for spec in DEFAULT_INFRASTRUCTURE_CHECKS
    )


def test_execution_spec_owns_mandatory_not_definition() -> None:
    assert "mandatory" not in (
        APPLICATION_FUNCTIONAL_VALIDATION.model_fields
    )

    optional = CheckExecutionSpec(
        definition=APPLICATION_FUNCTIONAL_VALIDATION,
        mandatory=False,
    )

    assert optional.mandatory is False
    assert (
        optional.definition
        is APPLICATION_FUNCTIONAL_VALIDATION
    )


def test_application_generator_consumes_canonical_execution_spec() -> None:
    spec = CheckExecutionSpec(
        definition=APPLICATION_FUNCTIONAL_VALIDATION,
        mandatory=False,
    )

    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=_application_behaviour(),
        tests=(spec,),
    )

    events = asyncio.run(
        _collect(
            generator,
            _context(),
        )
    )

    assert len(events) == 2

    planned = events[0].data["test"]
    executed = events[1].data["test"]

    assert planned["test_type"] == "functional_validation"
    assert planned["name"] == "Service functional validation"
    assert planned["mandatory"] is False

    assert executed["test_type"] == planned["test_type"]
    assert executed["name"] == planned["name"]
    assert executed["mandatory"] is False
    assert executed["result"] == "passed"

    # P1B preserves the existing evidence contract.
    assert "check_definition_id" not in planned
    assert "check_definition_id" not in executed


def test_infrastructure_generator_consumes_canonical_execution_spec() -> None:
    spec = CheckExecutionSpec(
        definition=INFRASTRUCTURE_CONNECTIVITY,
        mandatory=True,
    )

    context = _context()
    context.scenario_state = OperationalState.OBSERVING

    behaviour = ScenarioBehaviour(
        behaviour_id="fixture_p1b_infrastructure_observing",
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="all_required_checks_pass",
    )

    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=behaviour,
        checks=(spec,),
    )

    events = asyncio.run(
        _collect(
            generator,
            context,
        )
    )

    assert len(events) == 2

    test_data = events[1].data["test"]

    assert test_data["test_type"] == "connectivity"
    assert test_data["name"] == "Service connectivity validation"
    assert test_data["mandatory"] is True
    assert test_data["result"] == "passed"
    assert "check_definition_id" not in test_data


def test_application_generator_rejects_infrastructure_definition() -> None:
    with pytest.raises(
        ValueError,
        match="application",
    ):
        ApplicationTestGenerator(
            ids=IdFactory(),
            behaviour=_application_behaviour(),
            tests=(
                CheckExecutionSpec(
                    definition=INFRASTRUCTURE_CONNECTIVITY,
                ),
            ),
        )


def test_infrastructure_generator_rejects_application_definition() -> None:
    with pytest.raises(
        ValueError,
        match="infrastructure",
    ):
        InfrastructureTestGenerator(
            ids=IdFactory(),
            behaviour=_infrastructure_behaviour(),
            checks=(
                CheckExecutionSpec(
                    definition=APPLICATION_FUNCTIONAL_VALIDATION,
                ),
            ),
        )


def test_application_catalogue_uses_conservative_service_applicability() -> None:
    assert (
        APPLICATION_FUNCTIONAL_VALIDATION
        .applicability.service_classes
    ) == {
        ServiceClass.BUSINESS_APPLICATION,
        ServiceClass.BUSINESS_SERVICE,
    }

    assert (
        APPLICATION_TRANSACTION_PROCESSING
        .applicability.service_classes
    ) == {
        ServiceClass.BUSINESS_APPLICATION,
        ServiceClass.BUSINESS_SERVICE,
    }

    assert (
        APPLICATION_POST_DEPLOYMENT_SMOKE
        .applicability.service_classes
    ) == {
        ServiceClass.BUSINESS_APPLICATION,
    }


def test_infrastructure_catalogue_uses_conservative_applicability() -> None:
    connectivity = (
        INFRASTRUCTURE_CONNECTIVITY.applicability
    )

    assert connectivity.asset_classes == {
        AssetClass.DATABASE,
        AssetClass.MIDDLEWARE,
        AssetClass.LINUX,
        AssetClass.WINDOWS,
        AssetClass.MAINFRAME,
        AssetClass.NETWORK,
        AssetClass.DIGITAL_INFRASTRUCTURE,
    }

    # A generic connectivity probe is not automatically
    # meaningful for every information-security control.
    assert (
        AssetClass.INFORMATION_SECURITY
        not in connectivity.asset_classes
    )

    service_health = (
        INFRASTRUCTURE_SERVICE_HEALTH.applicability
    )

    assert service_health.asset_classes == {
        AssetClass.DATABASE,
        AssetClass.MIDDLEWARE,
        AssetClass.LINUX,
        AssetClass.WINDOWS,
        AssetClass.MAINFRAME,
        AssetClass.NETWORK,
        AssetClass.DIGITAL_INFRASTRUCTURE,
        AssetClass.INFORMATION_SECURITY,
    }

    dependency_connectivity = (
        INFRASTRUCTURE_DEPENDENCY_CONNECTIVITY
        .applicability
    )

    assert dependency_connectivity.service_classes == {
        ServiceClass.BUSINESS_APPLICATION,
        ServiceClass.BUSINESS_SERVICE,
        ServiceClass.INFRASTRUCTURE_SERVICE,
    }

    assert not dependency_connectivity.asset_classes


def test_generators_no_longer_own_duplicate_definition_types() -> None:
    import synthetic_ops_generator.generators.application_test as app_module
    import synthetic_ops_generator.generators.infrastructure_test as infra_module

    assert not hasattr(
        app_module,
        "ApplicationTestDefinition",
    )

    assert not hasattr(
        infra_module,
        "InfrastructureCheckDefinition",
    )
