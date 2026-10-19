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


class RecordingPublisher:
    def __init__(self) -> None:
        self.events = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _load():
    scenario = load_scenario(
        CONFIG_ROOT
        / "scenarios"
        / "insurance"
        / "INS-04.yaml"
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


def test_ins_04_declares_claims_payment_dependency_scope() -> None:
    scenario, _ = _load()

    assert scenario.scenario_id == "INS-04"
    assert scenario.family.value == "root_cause_analysis"
    assert scenario.industry.value == "insurance"

    assert scenario.target.enterprise_id == "insurer_alpha"
    assert scenario.target.business_stream_id == "claims"
    assert scenario.target.service_id == "claims_service"
    assert scenario.target.component_ids == [
        "claims_api",
    ]
    assert scenario.target.environment.value == "production"

    assert scenario.correlation.change_required is False

    assert scenario.trigger.source == SourceDomain.METRIC
    assert (
        scenario.trigger.trigger_type
        == "claims_payment_dependency_degradation"
    )

    assert [
        state.value
        for state in scenario.state_sequence
    ] == [
        "initialising",
        "normal",
        "warning",
        "degraded",
        "recovery",
        "completed",
    ]


def test_ins_04_separates_healthy_claims_from_payment_degradation() -> None:
    scenario, _ = _load()
    behaviours = _behaviour_map(scenario)

    normal_claims = behaviours[
        "metric_normal_claims_processing_healthy"
    ]

    assert normal_claims.source == SourceDomain.METRIC
    assert normal_claims.profile_id == "healthy_baseline"
    assert normal_claims.execution_node_id is None
    assert normal_claims.selection is not None
    assert normal_claims.selection.metric_ids == [
        "request_latency",
        "error_rate",
        "availability",
    ]

    warning_payment = behaviours[
        "metric_warning_claims_payment_warning"
    ]

    assert warning_payment.source == SourceDomain.METRIC
    assert warning_payment.profile_id == "operational_warning"
    assert (
        warning_payment.execution_node_id
        == "claims_payment_api"
    )
    assert warning_payment.selection is not None
    assert warning_payment.selection.metric_ids == [
        "request_latency",
        "queue_depth",
    ]

    degraded_claims = behaviours[
        "metric_degraded_claims_processing_healthy"
    ]

    assert degraded_claims.profile_id == "healthy_baseline"
    assert degraded_claims.execution_node_id is None
    assert degraded_claims.selection is not None
    assert degraded_claims.selection.metric_ids == [
        "request_latency",
        "error_rate",
        "availability",
    ]

    degraded_payment = behaviours[
        "metric_degraded_claims_payment_degradation"
    ]

    assert degraded_payment.profile_id == (
        "operational_degradation"
    )
    assert (
        degraded_payment.execution_node_id
        == "claims_payment_api"
    )
    assert degraded_payment.selection is not None
    assert degraded_payment.selection.metric_ids == [
        "request_latency",
        "queue_depth",
    ]

    dependency_logs = behaviours[
        "log_degraded_claims_api_dependency_errors"
    ]

    assert dependency_logs.source == SourceDomain.LOG
    assert dependency_logs.profile_id == (
        "degradation_error_logs"
    )
    assert (
        dependency_logs.execution_node_id
        == "claims_api"
    )

    assert not any(
        behaviour.source
        in {
            SourceDomain.ITSM,
            SourceDomain.DEPLOYMENT,
        }
        for behaviour in scenario.behaviours
    )


def test_ins_04_execution_plan_preserves_dependency_scopes() -> None:
    scenario, enterprise = _load()

    plan = build_scenario_execution_plan(
        scenario=scenario,
        enterprise=enterprise,
    )

    entries = {
        entry.behaviour.behaviour_id: entry
        for entry in plan.entries
    }

    payment_entry = entries[
        "metric_degraded_claims_payment_degradation"
    ]

    assert payment_entry.execution_target is not None
    assert (
        payment_entry.execution_target.business_stream
        == "claims"
    )
    assert (
        payment_entry.execution_target.service
        == "claims_payment_service"
    )
    assert (
        payment_entry.execution_target.component
        == "claims_payment_api"
    )

    claims_log_entry = entries[
        "log_degraded_claims_api_dependency_errors"
    ]

    assert claims_log_entry.execution_target is not None
    assert (
        claims_log_entry.execution_target.service
        == "claims_service"
    )
    assert (
        claims_log_entry.execution_target.component
        == "claims_api"
    )


def test_ins_04_oracle_keeps_root_cause_out_of_runtime_truth() -> None:
    scenario, _ = _load()
    expected = scenario.expected_result

    assert expected.expected_decision is None
    assert expected.expected_action is None
    assert expected.expected_outcome.value == "successful"

    assert expected.expected_root_cause == (
        "claims_payment_service"
    )

    assert expected.expected_incident_attribution is False

    assert set(
        expected.expected_blocking_conditions
    ) == {
        "claims_payment_latency_blocking",
        "claims_payment_queue_depth_blocking",
    }


def test_ins_04_runtime_emits_differentiated_dependency_evidence() -> None:
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
                14,
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
        )

        return publisher.events

    events = asyncio.run(execute())

    assert events

    assert {
        event.chg_id
        for event in events
    } == {None}

    metric_events = [
        event
        for event in events
        if event.source_domain == SourceDomain.METRIC
    ]

    degraded_payment_metrics = [
        event
        for event in metric_events
        if (
            event.service == "claims_payment_service"
            and event.component is None
            and event.data["metric"]["scenario_state"]
            == "degraded"
        )
    ]

    assert {
        event.data["metric"]["metric_definition_id"]
        for event in degraded_payment_metrics
    } == {
        "request_latency",
        "queue_depth",
    }

    assert {
        event.data["metric"]["classification"]
        for event in degraded_payment_metrics
    } == {
        "blocking",
    }

    assert {
        event.data["metric"]["baseline_profile_id"]
        for event in degraded_payment_metrics
    } == {
        "claims_payment_nominal",
    }

    assert {
        event.data["metric"]["benchmark_profile_id"]
        for event in degraded_payment_metrics
    } == {
        "critical_interactive_transaction",
    }

    queue_event = next(
        event
        for event in degraded_payment_metrics
        if (
            event.data["metric"]["metric_definition_id"]
            == "queue_depth"
        )
    )

    queue_metric = queue_event.data["metric"]

    assert (
        queue_metric["observed_value"]
        == queue_metric[
            "effective_benchmark"
        ]["blocking_threshold"]
    )

    degraded_claims_metrics = [
        event
        for event in metric_events
        if (
            event.service == "claims_service"
            and event.data["metric"]["scenario_state"]
            == "degraded"
        )
    ]

    assert {
        event.data["metric"]["metric_definition_id"]
        for event in degraded_claims_metrics
    } == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert {
        event.data["metric"]["classification"]
        for event in degraded_claims_metrics
    } == {
        "normal",
    }

    log_events = [
        event
        for event in events
        if (
            event.source_domain == SourceDomain.LOG
            and event.service == "claims_service"
            and event.component == "claims_api"
        )
    ]

    assert {
        event.data["log"]["error_code"]
        for event in log_events
        if event.data["log"]["error_code"] is not None
    } >= {
        "REQUEST_TIMEOUT",
        "DEPENDENCY_ERROR",
    }

    recovery_payment_metrics = [
        event
        for event in metric_events
        if (
            event.service == "claims_payment_service"
            and event.data["metric"]["scenario_state"]
            == "recovery"
        )
    ]

    assert {
        event.data["metric"]["metric_definition_id"]
        for event in recovery_payment_metrics
    } == {
        "request_latency",
        "queue_depth",
    }

    assert {
        event.data["metric"]["classification"]
        for event in recovery_payment_metrics
    } == {
        "normal",
    }

    recovery_logs = [
        event
        for event in events
        if (
            event.source_domain == SourceDomain.LOG
            and event.service == "claims_service"
            and event.component == "claims_api"
            and event.behaviour_id
            == "log_recovery_claims_api_dependency_recovery"
        )
    ]

    assert recovery_logs

    assert all(
        "expected_root_cause"
        not in event.data
        for event in events
    )
