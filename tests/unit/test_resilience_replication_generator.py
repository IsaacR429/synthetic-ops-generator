from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.core.randomness import SimulationRandom
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
    SourceDomain,
)
from synthetic_ops_generator.domain.resilience import (
    ReplicationObservation,
    ReplicationStatus,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.generators.resilience import (
    ResilienceGenerator,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioResilienceReplication,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    REPLICATION_OBSERVED,
    SUPPORTED_PROFILES_BY_SOURCE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"

BASE_TIME = datetime(
    2026,
    10,
    19,
    12,
    0,
    tzinfo=UTC,
)


def build_context(
    *,
    state: OperationalState = OperationalState.REMEDIATION,
) -> ScenarioContext:
    return ScenarioContext(
        scenario_id="BANK-06-T3A2B2",
        run_id="RUN-T3A2B2-001",
        chg_id=None,
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_primary",
        service_instance_id="payment_api_primary",
        risk=RiskLevel.CRITICAL,
        scenario_state=state,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_replication_target() -> ScenarioExecutionTarget:
    return ScenarioExecutionTarget(
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        site_id="bank_secondary",
        service_instance_id="payment_api_secondary",
    )


def build_behaviour(
    *,
    status: ReplicationStatus = ReplicationStatus.LAGGING,
    offset_seconds: float | None = 120.0,
    include_replication: bool = True,
) -> ScenarioBehaviour:
    replication = (
        ScenarioResilienceReplication(
            to_execution_node_id="payment_api_secondary",
            replication_status=status,
            last_successful_replication_offset_seconds=(
                offset_seconds
            ),
        )
        if include_replication
        else None
    )

    return ScenarioBehaviour(
        behaviour_id=(
            "fixture_test_resilience_replication_generator_01"
        ),
        source=SourceDomain.RESILIENCE,
        during_state=OperationalState.REMEDIATION,
        profile_id=REPLICATION_OBSERVED,
        execution_node_id="payment_api_primary",
        resilience_replication=replication,
    )


async def collect_events(
    generator: ResilienceGenerator,
    context: ScenarioContext,
):
    return [
        event
        async for event in generator.generate(context)
    ]


def test_replication_profile_is_registered_centrally() -> None:
    assert (
        REPLICATION_OBSERVED
        in SUPPORTED_PROFILES_BY_SOURCE[
            SourceDomain.RESILIENCE
        ]
    )


def test_replication_profile_emits_factual_observation() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        replication_target=build_replication_target(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )

    assert len(events) == 1

    event = events[0]

    assert (
        event.event_type
        == "resilience.replication_observed"
    )
    assert event.source_system == "synthetic_resilience"
    assert event.source_domain == SourceDomain.RESILIENCE

    observation = ReplicationObservation.model_validate(
        event.data["replication_observation"]
    )

    assert observation.service == "payment_service"
    assert observation.component == "payment_api"

    assert observation.from_site_id == "bank_primary"
    assert (
        observation.from_service_instance_id
        == "payment_api_primary"
    )

    assert observation.to_site_id == "bank_secondary"
    assert (
        observation.to_service_instance_id
        == "payment_api_secondary"
    )

    assert (
        observation.replication_status
        == ReplicationStatus.LAGGING
    )

    assert observation.observed_at == BASE_TIME

    assert (
        observation.last_successful_replication_at
        == BASE_TIME - timedelta(seconds=120)
    )


def test_replication_event_envelope_remains_on_source_instance() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        replication_target=build_replication_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )[0]

    assert event.site_id == "bank_primary"
    assert (
        event.service_instance_id
        == "payment_api_primary"
    )

    observation = ReplicationObservation.model_validate(
        event.data["replication_observation"]
    )

    assert observation.to_site_id == "bank_secondary"


def test_replication_profile_allows_unknown_last_success() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            status=ReplicationStatus.UNKNOWN,
            offset_seconds=None,
        ),
        replication_target=build_replication_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )[0]

    observation = ReplicationObservation.model_validate(
        event.data["replication_observation"]
    )

    assert (
        observation.replication_status
        == ReplicationStatus.UNKNOWN
    )
    assert (
        observation.last_successful_replication_at
        is None
    )


def test_replication_profile_requires_replication_configuration() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(
            include_replication=False,
        ),
        replication_target=build_replication_target(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "replication profile requires "
            "replication configuration"
        ),
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )


def test_replication_profile_requires_resolved_replication_target() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "replication profile requires "
            "a replication target"
        ),
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )


def test_replication_profile_rejects_transition_target() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        transition_target=build_replication_target(),
        replication_target=build_replication_target(),
    )

    with pytest.raises(
        ValueError,
        match=(
            "replication profile cannot use "
            "a transition target"
        ),
    ):
        asyncio.run(
            collect_events(
                generator,
                build_context(),
            )
        )


def test_replication_generator_does_not_run_outside_behaviour_state() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        replication_target=build_replication_target(),
    )

    events = asyncio.run(
        collect_events(
            generator,
            build_context(
                state=OperationalState.RECOVERY,
            ),
        )
    )

    assert events == []


def test_replication_payload_remains_factual_only() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        replication_target=build_replication_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )[0]

    payload = event.data["replication_observation"]

    forbidden = {
        "rpo_actual",
        "rpo_met",
        "data_loss",
        "data_loss_duration",
        "dr_success",
        "recovery_success",
        "compliant",
        "blocking",
        "decision",
        "residual_risk",
    }

    assert forbidden.isdisjoint(payload)


def test_factory_binding_propagates_replication_peer() -> None:
    enterprise = load_enterprise(
        CONFIG_ROOT
        / "enterprises"
        / "bank_alpha"
    )

    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "banking"
        / "BANK-03.yaml"
    )

    behaviour = ScenarioBehaviour(
        behaviour_id=(
            "fixture_test_resilience_replication_generator_02"
        ),
        source=SourceDomain.RESILIENCE,
        during_state=scenario.behaviours[0].during_state,
        profile_id=REPLICATION_OBSERVED,
        execution_node_id="payment_api_primary",
        resilience_replication=(
            ScenarioResilienceReplication(
                to_execution_node_id=(
                    "payment_api_secondary"
                ),
                replication_status=(
                    ReplicationStatus.LAGGING
                ),
                last_successful_replication_offset_seconds=(
                    120.0
                ),
            )
        ),
    )

    scenario = scenario.model_copy(
        update={
            "behaviours": [
                behaviour,
            ],
        }
    )

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    entry = plan.entries[0]

    assert entry.resilience_replication_target is not None

    bindings = GeneratorFactory(
        config_root=CONFIG_ROOT
    ).build_execution_bindings(
        scenario=scenario,
        enterprise=enterprise,
        plan=plan,
        ids=IdFactory(),
        random_source=SimulationRandom(42),
        event_history=[],
    )

    assert len(bindings) == 1

    binding = bindings[0]

    assert isinstance(
        binding.generator,
        ResilienceGenerator,
    )

    assert (
        binding.resilience_replication_target
        == entry.resilience_replication_target
    )

    context = build_context(
        state=behaviour.during_state,
    )

    event = asyncio.run(
        collect_events(
            binding.generator,
            context,
        )
    )[0]

    observation = ReplicationObservation.model_validate(
        event.data["replication_observation"]
    )

    assert (
        observation.to_service_instance_id
        == "payment_api_secondary"
    )


def test_replication_observation_uses_central_id_and_event_time() -> None:
    generator = ResilienceGenerator(
        ids=IdFactory(),
        behaviour=build_behaviour(),
        replication_target=build_replication_target(),
    )

    event = asyncio.run(
        collect_events(
            generator,
            build_context(),
        )
    )[0]

    observation = ReplicationObservation.model_validate(
        event.data["replication_observation"]
    )

    assert observation.observation_id == "RSO0000001"
    assert observation.observed_at == event.event_time
    assert event.event_time == BASE_TIME
