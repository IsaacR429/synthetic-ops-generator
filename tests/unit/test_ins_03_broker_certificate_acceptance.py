import asyncio
from datetime import UTC, datetime
from pathlib import Path

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.core.randomness import (
    SimulationRandom,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
    SourceDomain,
)
from synthetic_ops_generator.generators.factory import (
    GeneratorFactory,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    build_scenario_execution_plan,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.runner import (
    ScenarioRunner,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_ROOT = PROJECT_ROOT / "config"

SCENARIO_PATH = (
    CONFIG_ROOT
    / "scenarios"
    / "insurance"
    / "INS-03.yaml"
)


class RecordingPublisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _load():
    scenario = load_scenario(
        SCENARIO_PATH
    )

    enterprise = load_enterprise_configuration(
        CONFIG_ROOT
        / "enterprises"
        / "insurer_alpha"
    )

    return scenario, enterprise


def test_ins_03_declares_broker_portal_predeployment_scope() -> None:
    scenario, _ = _load()

    assert scenario.scenario_id == "INS-03"
    assert scenario.industry.value == "insurance"
    assert scenario.family.value == "change_validation"

    assert (
        scenario.target.enterprise_id
        == "insurer_alpha"
    )
    assert (
        scenario.target.business_stream_id
        == "customer_broker"
    )
    assert (
        scenario.target.service_id
        == "broker_portal"
    )
    assert scenario.target.component_ids == [
        "broker_web"
    ]
    assert scenario.target.environment.value == "production"

    assert scenario.correlation.change_required is True

    assert (
        scenario.trigger.source
        == SourceDomain.INFRASTRUCTURE_TEST
    )

    assert [
        state.value
        for state in scenario.state_sequence
    ] == [
        "initialising",
        "normal",
        "degraded",
        "failure",
        "remediation",
        "recovery",
        "completed",
    ]


def test_ins_03_has_approved_change_and_no_deployment_behaviour() -> None:
    scenario, _ = _load()

    itsm = [
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.ITSM
    ]

    assert len(itsm) == 1
    assert itsm[0].profile_id == "approved_change"

    deployment = [
        behaviour
        for behaviour in scenario.behaviours
        if behaviour.source == SourceDomain.DEPLOYMENT
    ]

    assert deployment == []


def test_ins_03_declares_pass_then_certificate_failure_checks() -> None:
    scenario, _ = _load()

    infrastructure = [
        behaviour
        for behaviour in scenario.behaviours
        if (
            behaviour.source
            == SourceDomain.INFRASTRUCTURE_TEST
        )
    ]

    assert len(infrastructure) == 2

    passing, failing = infrastructure

    assert (
        passing.profile_id
        == "all_required_checks_pass"
    )
    assert passing.during_state.value == "normal"
    assert passing.execution_node_id == "broker_web"
    assert (
        passing.check_selection.check_definition_ids
        == [
            "infrastructure.dependency_connectivity",
            "infrastructure.dns_resolution",
        ]
    )

    assert (
        failing.profile_id
        == "required_check_failed"
    )
    assert failing.during_state.value == "failure"
    assert failing.execution_node_id == "broker_web"
    assert (
        failing.check_selection.check_definition_ids
        == [
            "infrastructure.certificate_validation",
        ]
    )


def test_ins_03_oracle_preserves_fail_remediate_boundary() -> None:
    scenario, _ = _load()

    oracle = scenario.expected_result

    assert oracle.scenario_id == "INS-03"
    assert oracle.expected_decision.value == "fail"
    assert oracle.expected_action.value == "remediate"
    assert oracle.expected_outcome.value == "failed"

    assert (
        "mandatory_certificate_validation_failed"
        in oracle.expected_blocking_conditions
    )

    assert oracle.expected_incident_attribution is False


def test_ins_03_runtime_emits_expected_predeployment_evidence() -> None:
    async def execute():
        scenario, enterprise = _load()

        plan = build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )

        ids = IdFactory()

        bindings = GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build_execution_bindings(
            scenario=scenario,
            enterprise=enterprise,
            plan=plan,
            ids=ids,
            random_source=SimulationRandom(42),
            event_history=[],
        )

        clock = ManualSimulationClock(
            datetime(
                2026,
                10,
                19,
                10,
                0,
                tzinfo=UTC,
            )
        )

        runner = ScenarioRunner(
            ids=ids,
            clock=clock,
        )

        context = runner.create_context(
            scenario=scenario,
            enterprise=enterprise,
            random_seed=42,
        )

        publisher = RecordingPublisher()

        await runner.execute_bindings(
            scenario=scenario,
            context=context,
            bindings=bindings,
            publisher=publisher,
            stop_at_state=OperationalState.FAILURE,
        )

        return publisher.events

    events = asyncio.run(
        execute()
    )

    assert events

    approval_events = [
        event
        for event in events
        if event.event_type == "itsm.approval.approved"
    ]

    assert len(approval_events) == 1

    executed_tests = [
        event
        for event in events
        if event.event_type
        in {
            "infrastructure_test.passed",
            "infrastructure_test.failed",
        }
    ]

    assert [
        event.data["test"]["check_definition_id"]
        for event in executed_tests
    ] == [
        "infrastructure.dependency_connectivity",
        "infrastructure.dns_resolution",
        "infrastructure.certificate_validation",
    ]

    assert [
        event.data["test"]["result"]
        for event in executed_tests
    ] == [
        "passed",
        "passed",
        "failed",
    ]

    assert {
        event.service
        for event in executed_tests
    } == {
        "broker_portal"
    }

    assert {
        event.component
        for event in executed_tests
    } == {
        "broker_web"
    }

    assert not any(
        event.event_type.startswith("deployment.")
        for event in events
    )

    certificate_failure = executed_tests[-1]

    assert (
        certificate_failure.event_type
        == "infrastructure_test.failed"
    )

    forbidden_oracle_fields = {
        "expected_decision",
        "expected_action",
        "expected_outcome",
        "implementation_blocked",
        "remediation_action",
    }

    assert forbidden_oracle_fields.isdisjoint(
        certificate_failure.data
    )
