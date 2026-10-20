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
    / "INS-05.yaml"
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


def _behaviour_map(scenario):
    return {
        behaviour.behaviour_id: behaviour
        for behaviour in scenario.behaviours
    }


def test_ins_05_declares_high_risk_claims_change_scope() -> None:
    scenario, _ = _load()

    assert scenario.scenario_id == "INS-05"
    assert scenario.family.value == "change_validation"
    assert scenario.industry.value == "insurance"

    assert scenario.target.enterprise_id == "insurer_alpha"
    assert scenario.target.business_stream_id == "claims"
    assert scenario.target.service_id == "claims_service"
    assert scenario.target.component_ids == [
        "claims_api",
        "claims_database",
    ]
    assert scenario.target.environment.value == "production"

    assert scenario.risk.value == "high"
    assert scenario.correlation.change_required is True

    assert scenario.trigger.source == SourceDomain.DEPLOYMENT
    assert scenario.trigger.trigger_type == "claims_service_release"

    assert [
        state.value
        for state in scenario.state_sequence
    ] == [
        "initialising",
        "normal",
        "implementing",
        "observing",
        "completed",
    ]


def test_ins_05_declares_healthy_release_with_pending_business_validation() -> None:
    scenario, _ = _load()
    behaviours = _behaviour_map(scenario)

    assert (
        behaviours[
            "itsm_normal_approved_change"
        ].profile_id
        == "approved_change"
    )

    assert (
        behaviours[
            "infrastructure_test_normal_all_required_checks_pass"
        ].profile_id
        == "all_required_checks_pass"
    )

    assert (
        behaviours[
            "deployment_implementing_successful_deployment"
        ].profile_id
        == "successful_deployment"
    )

    assert (
        behaviours[
            "application_test_observing_all_mandatory_tests_pass"
        ].profile_id
        == "all_mandatory_tests_pass"
    )

    assert (
        behaviours[
            "metric_observing_healthy_post_change"
        ].profile_id
        == "healthy_post_change"
    )

    manual = behaviours[
        "manual_validation_observing_required_business_validation_pending"
    ]

    assert manual.source == SourceDomain.MANUAL_VALIDATION
    assert (
        manual.profile_id
        == "required_business_validation_pending"
    )

    evidence = behaviours[
        "evidence_observing_pending_business_validation_evidence"
    ]

    assert evidence.source == SourceDomain.EVIDENCE
    assert (
        evidence.profile_id
        == "pending_business_validation_evidence"
    )

    behaviour_ids = [
        behaviour.behaviour_id
        for behaviour in scenario.behaviours
    ]

    assert behaviour_ids.index(
        "manual_validation_observing_required_business_validation_pending"
    ) < behaviour_ids.index(
        "evidence_observing_pending_business_validation_evidence"
    )


def test_ins_05_oracle_separates_incomplete_decision_from_successful_outcome() -> None:
    scenario, _ = _load()

    oracle = scenario.expected_result

    assert oracle.scenario_id == "INS-05"
    assert oracle.expected_decision.value == "incomplete"
    assert oracle.expected_action.value == "review"
    assert oracle.expected_outcome.value == "successful"

    assert oracle.expected_blocking_conditions == [
        "required_business_validation_pending",
    ]

    assert oracle.expected_incident_attribution is False
    assert oracle.expected_root_cause is None

    assert set(
        oracle.expected_evidence
    ) == {
        "change_approval",
        "infrastructure_validation",
        "deployment_result",
        "application_validation",
        "pre_change_baseline",
        "post_change_observation",
        "business_validation_request",
    }


def test_ins_05_runtime_keeps_business_validation_pending() -> None:
    async def execute():
        scenario, enterprise = _load()

        plan = build_scenario_execution_plan(
            scenario=scenario,
            enterprise=enterprise,
        )

        ids = IdFactory()

        clock = ManualSimulationClock(
            datetime(
                2026,
                10,
                20,
                9,
                0,
                tzinfo=UTC,
            )
        )

        runner = ScenarioRunner(
            ids=ids,
            clock=clock,
        )

        bindings = GeneratorFactory(
            config_root=CONFIG_ROOT
        ).build_execution_bindings(
            scenario=scenario,
            enterprise=enterprise,
            plan=plan,
            ids=ids,
            random_source=SimulationRandom(42),
            event_history=runner.event_history,
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
        )

        return (
            scenario,
            publisher.events,
        )

    scenario, events = asyncio.run(
        execute()
    )

    assert events

    change_ids = {
        event.chg_id
        for event in events
    }

    assert len(change_ids) == 1
    assert None not in change_ids

    assert any(
        event.event_type == "itsm.approval.approved"
        for event in events
    )

    assert any(
        event.event_type == "cicd.deployment.completed"
        for event in events
    )

    infrastructure_events = [
        event
        for event in events
        if event.source_domain
        == SourceDomain.INFRASTRUCTURE_TEST
    ]

    assert infrastructure_events

    infrastructure_results = [
        event
        for event in infrastructure_events
        if event.event_type
        in {
            "infrastructure_test.passed",
            "infrastructure_test.failed",
        }
    ]

    assert infrastructure_results
    assert all(
        event.event_type == "infrastructure_test.passed"
        for event in infrastructure_results
    )

    application_events = [
        event
        for event in events
        if event.source_domain
        == SourceDomain.APPLICATION_TEST
    ]

    assert application_events

    application_results = [
        event
        for event in application_events
        if event.event_type
        in {
            "application_test.passed",
            "application_test.failed",
        }
    ]

    assert application_results
    assert all(
        event.event_type == "application_test.passed"
        for event in application_results
    )

    manual_events = [
        event
        for event in events
        if event.source_domain
        == SourceDomain.MANUAL_VALIDATION
    ]

    assert len(manual_events) == 1

    manual_request = manual_events[0]

    assert (
        manual_request.event_type
        == "manual_validation.requested"
    )

    validation = manual_request.data["validation"]

    assert validation["validation_type"] == "business_validation"
    assert validation["mandatory"] is True
    assert validation["status"] == "pending"
    assert validation["result"] is None
    assert validation["completed_at"] is None
    assert validation["validated_by"] is None

    assert not any(
        event.event_type == "manual_validation.completed"
        for event in events
    )

    assert not any(
        event.event_type == "itsm.incident.created"
        for event in events
    )

    evidence_events = [
        event
        for event in events
        if event.source_domain == SourceDomain.EVIDENCE
    ]

    evidence_by_type = {
        event.data["evidence"]["evidence_type"]: event
        for event in evidence_events
    }

    assert set(evidence_by_type) == {
        "change_approval",
        "infrastructure_validation",
        "deployment_result",
        "application_validation",
        "pre_change_baseline",
        "post_change_observation",
        "business_validation_request",
    }

    request_evidence = evidence_by_type[
        "business_validation_request"
    ]

    assert request_evidence.data[
        "evidence"
    ]["source_event_ids"] == [
        manual_request.event_id
    ]

    forbidden_oracle_fields = {
        "expected_decision",
        "expected_action",
        "expected_outcome",
        "expected_blocking_conditions",
        "expected_root_cause",
    }

    assert all(
        forbidden_oracle_fields.isdisjoint(
            event.data
        )
        for event in events
    )

    assert scenario.expected_result.expected_decision.value == (
        "incomplete"
    )
    assert scenario.expected_result.expected_outcome.value == (
        "successful"
    )
