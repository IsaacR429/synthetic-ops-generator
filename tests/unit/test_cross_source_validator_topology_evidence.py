from datetime import UTC, datetime, timedelta

from synthetic_ops_generator.domain.enterprise import (
    BusinessStream,
    Component,
    Enterprise,
    Service,
)
from synthetic_ops_generator.domain.enums import (
    Criticality,
    Environment,
    Industry,
    OperationalState,
    Outcome,
    RiskLevel,
    SourceDomain,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.oracle.models import (
    ExpectedScenarioResult,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.execution_plan import (
    ScenarioExecutionPlan,
    ScenarioExecutionPlanEntry,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    ScenarioDefinition,
    ScenarioFamily,
    ScenarioTarget,
    ScenarioTrigger,
)
from synthetic_ops_generator.validation.cross_source import (
    CrossSourceValidator,
)

BASE_TIME = datetime(
    2026,
    8,
    13,
    10,
    0,
    tzinfo=UTC,
)


def build_enterprise() -> Enterprise:
    return Enterprise(
        enterprise_id="bank_alpha",
        name="Bank Alpha",
        industry=Industry.BANKING,
        business_streams=[
            BusinessStream(
                stream_id="payments",
                name="Payments",
            ),
        ],
        services=[
            Service(
                service_id="payment_service",
                name="Payment Service",
                business_stream_id="payments",
                owner="Payments Team",
                criticality=Criticality.CRITICAL,
            ),
        ],
        components=[
            Component(
                component_id="payment_api",
                name="Payment API",
                component_type="api",
                service_id="payment_service",
                environment=Environment.PRODUCTION,
            ),
        ],
    )


def build_context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="TEST-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=BASE_TIME,
        random_seed=42,
    )


def build_event(
    *,
    sequence_number: int,
    component: str | None = None,
) -> GeneratedEvent:
    return GeneratedEvent(
        event_id=f"EVT{sequence_number:07d}",
        event_type="test.event",
        event_time=(
            BASE_TIME
            + timedelta(seconds=sequence_number * 5)
        ),
        source_system="synthetic_test",
        scenario_id="TEST-01",
        run_id="RUN0000001",
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        component=component,
        environment=Environment.PRODUCTION,
        sequence_number=sequence_number,
    )


def build_deployment_event(
    *,
    sequence_number: int,
    event_type: str,
    deployment_id: str = "DEP0000001",
) -> GeneratedEvent:
    return build_event(
        sequence_number=sequence_number,
        component="payment_api",
    ).model_copy(
        update={
            "event_type": event_type,
            "data": {
                "deployment": {
                    "deployment_id": deployment_id,
                }
            },
        }
    )


def build_incident_event(
    *,
    sequence_number: int,
    event_type: str,
    incident_id: str = "INC0000001",
    chg_id: str = "CHG0000001",
    service: str = "payment_service",
    component: str | None = "payment_api",
) -> GeneratedEvent:
    return build_event(
        sequence_number=sequence_number,
        component=component,
    ).model_copy(
        update={
            "event_type": event_type,
            "chg_id": chg_id,
            "service": service,
            "component": component,
            "data": {
                "incident": {
                    "incident_id": incident_id,
                    "chg_id": chg_id,
                    "service": service,
                    "component": component,
                }
            },
        }
    )


def validate(
    events: list[GeneratedEvent],
):
    return CrossSourceValidator().validate(
        events=events,
        context=build_context(),
        enterprise=build_enterprise(),
    )


def test_valid_enterprise_references_pass() -> None:
    report = validate([
        build_event(
            sequence_number=1,
            component="payment_api",
        )
    ])

    assert report.is_valid is True


def test_unknown_business_stream_is_reported() -> None:
    event = build_event(sequence_number=1).model_copy(
        update={"business_stream": "unknown_stream"}
    )

    report = validate([event])

    assert any(
        finding.rule == "business_stream_reference"
        for finding in report.findings
    )


def test_unknown_service_is_reported() -> None:
    event = build_event(sequence_number=1).model_copy(
        update={"service": "unknown_service"}
    )

    report = validate([event])

    assert any(
        finding.rule == "service_reference"
        for finding in report.findings
    )


def test_service_business_stream_mismatch_is_reported() -> None:
    event = build_event(sequence_number=1).model_copy(
        update={"business_stream": "unknown_stream"}
    )

    enterprise = build_enterprise()

    enterprise.business_streams.append(
        BusinessStream(
            stream_id="unknown_stream",
            name="Other Stream",
        )
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
    )

    assert any(
        finding.rule
        == "service_business_stream_relationship"
        for finding in report.findings
    )


def test_unknown_component_is_reported() -> None:
    event = build_event(
        sequence_number=1,
        component="unknown_component",
    )

    report = validate([event])

    assert any(
        finding.rule == "component_reference"
        for finding in report.findings
    )


def test_component_service_mismatch_is_reported() -> None:
    enterprise = build_enterprise()

    enterprise.components[0] = (
        enterprise.components[0].model_copy(
            update={"service_id": "other_service"}
        )
    )

    event = build_event(
        sequence_number=1,
        component="payment_api",
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
    )

    assert any(
        finding.rule
        == "component_service_relationship"
        for finding in report.findings
    )


def test_component_environment_mismatch_is_reported() -> None:
    event = build_event(
        sequence_number=1,
        component="payment_api",
    ).model_copy(
        update={"environment": Environment.TEST}
    )

    report = validate([event])

    assert any(
        finding.rule
        == "component_environment_relationship"
        for finding in report.findings
    )


def test_valid_evidence_reference_passes() -> None:
    source_event = build_event(sequence_number=1)

    evidence_event = build_event(
        sequence_number=2
    ).model_copy(
        update={
            "event_type": "evidence.captured",
            "data": {
                "evidence": {
                    "source_event_ids": [
                        source_event.event_id,
                    ],
                    "source_record_ids": [],
                }
            },
        }
    )

    report = validate([
        source_event,
        evidence_event,
    ])

    assert report.is_valid is True


def test_missing_evidence_event_reference_is_reported() -> None:
    evidence_event = build_event(
        sequence_number=2
    ).model_copy(
        update={
            "event_type": "evidence.captured",
            "data": {
                "evidence": {
                    "source_event_ids": [
                        "EVT9999999",
                    ],
                    "source_record_ids": [],
                }
            },
        }
    )

    report = validate([evidence_event])

    assert any(
        finding.rule == "evidence_event_reference"
        for finding in report.findings
    )


def test_future_evidence_reference_is_reported() -> None:
    evidence_event = build_event(
        sequence_number=1
    ).model_copy(
        update={
            "event_type": "evidence.captured",
            "data": {
                "evidence": {
                    "source_event_ids": [
                        "EVT0000002",
                    ],
                    "source_record_ids": [],
                }
            },
        }
    )

    future_event = build_event(sequence_number=2)

    report = validate([
        evidence_event,
        future_event,
    ])

    assert any(
        finding.rule
        == "evidence_reference_chronology"
        for finding in report.findings
    )


def test_valid_deployment_rollback_relationship_passes() -> None:
    context = build_context()
    context.deployment_id = "DEP0000001"

    events = [
        build_deployment_event(
            sequence_number=1,
            event_type="cicd.deployment.completed",
        ),
        build_deployment_event(
            sequence_number=2,
            event_type="cicd.deployment.rollback_started",
        ),
        build_deployment_event(
            sequence_number=3,
            event_type="cicd.deployment.rollback_completed",
        ),
    ]

    report = CrossSourceValidator().validate(
        events=events,
        context=context,
        enterprise=build_enterprise(),
    )

    assert report.is_valid is True
    assert report.findings == []


def test_rollback_without_prior_deployment_is_reported() -> None:
    context = build_context()
    context.deployment_id = "DEP0000001"

    events = [
        build_deployment_event(
            sequence_number=1,
            event_type="cicd.deployment.rollback_started",
        ),
        build_deployment_event(
            sequence_number=2,
            event_type="cicd.deployment.rollback_completed",
        ),
    ]

    report = CrossSourceValidator().validate(
        events=events,
        context=context,
        enterprise=build_enterprise(),
    )

    assert any(
        finding.rule
        == "rollback_deployment_relationship"
        for finding in report.findings
    )


def test_different_deployment_id_is_reported() -> None:
    context = build_context()
    context.deployment_id = "DEP0000001"

    event = build_deployment_event(
        sequence_number=1,
        event_type="cicd.deployment.completed",
        deployment_id="DEP9999999",
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=context,
        enterprise=build_enterprise(),
    )

    assert any(
        finding.rule == "deployment_correlation"
        for finding in report.findings
    )


def test_valid_incident_lifecycle_passes() -> None:
    context = build_context()
    context.incident_id = "INC0000001"

    events = [
        build_incident_event(
            sequence_number=1,
            event_type="itsm.incident.created",
        ),
        build_incident_event(
            sequence_number=2,
            event_type="itsm.incident.resolved",
        ),
    ]

    report = CrossSourceValidator().validate(
        events=events,
        context=context,
        enterprise=build_enterprise(),
    )

    assert report.is_valid is True
    assert report.findings == []


def test_incident_resolution_without_creation_is_reported() -> None:
    context = build_context()
    context.incident_id = "INC0000001"

    event = build_incident_event(
        sequence_number=1,
        event_type="itsm.incident.resolved",
    )

    report = CrossSourceValidator().validate(
        events=[event],
        context=context,
        enterprise=build_enterprise(),
    )

    assert any(
        finding.rule
        == "incident_resolution_relationship"
        for finding in report.findings
    )


def test_incident_lifecycle_field_mismatch_is_reported() -> None:
    context = build_context()
    context.incident_id = "INC0000001"

    created = build_incident_event(
        sequence_number=1,
        event_type="itsm.incident.created",
    )

    resolved = build_incident_event(
        sequence_number=2,
        event_type="itsm.incident.resolved",
        service="payment_service",
        component=None,
    )

    report = CrossSourceValidator().validate(
        events=[
            created,
            resolved,
        ],
        context=context,
        enterprise=build_enterprise(),
    )

    assert any(
        finding.rule
        == "incident_lifecycle_consistency"
        for finding in report.findings
    )


def build_multi_target_enterprise() -> Enterprise:
    enterprise = build_enterprise()
    enterprise.business_streams.append(
        BusinessStream(
            stream_id="core_banking",
            name="Core Banking",
        )
    )
    enterprise.services.append(
        Service(
            service_id="account_service",
            name="Account Service",
            business_stream_id="core_banking",
            owner="Core Banking Team",
            criticality=Criticality.CRITICAL,
        )
    )
    enterprise.components.append(
        Component(
            component_id="account_database",
            name="Account Database",
            component_type="database",
            service_id="account_service",
            environment=Environment.PRODUCTION,
        )
    )
    return enterprise


def build_target_execution_plan(
    target: ScenarioExecutionTarget | None,
) -> ScenarioExecutionPlan:
    behaviour = ScenarioBehaviour(
        source=SourceDomain.LOG,
        during_state=OperationalState.OBSERVING,
        profile_id="execution_target_test",
    )
    return ScenarioExecutionPlan(
        entries=(
            ScenarioExecutionPlanEntry(
                behaviour=behaviour,
                execution_target=target,
            ),
        )
    )


def test_execution_plan_target_is_valid_run_scope() -> None:
    execution_target = ScenarioExecutionTarget(
        business_stream="core_banking",
        service="account_service",
        component="account_database",
        environment=Environment.PRODUCTION,
    )
    event = build_event(
        sequence_number=1,
    ).model_copy(
        update={
            "business_stream": "core_banking",
            "service": "account_service",
            "component": "account_database",
        }
    )
    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=build_multi_target_enterprise(),
        execution_plan=build_target_execution_plan(
            execution_target
        ),
    )
    assert report.is_valid is True
    assert report.findings == []


def test_enterprise_known_target_outside_execution_plan_is_rejected() -> None:
    event = build_event(
        sequence_number=1,
    ).model_copy(
        update={
            "business_stream": "core_banking",
            "service": "account_service",
            "component": "account_database",
        }
    )
    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=build_multi_target_enterprise(),
        execution_plan=build_target_execution_plan(None),
    )
    assert report.is_valid is False
    assert any(
        finding.rule == "business_stream_correlation"
        or finding.rule == "service_correlation"
        for finding in report.findings
    )


def build_scope_scenario(
    component_ids: list[str],
) -> ScenarioDefinition:
    return ScenarioDefinition(
        scenario_id="TEST-01",
        name="Execution Scope Test",
        description="Tests declared execution scope.",
        family=ScenarioFamily.CHANGE_VALIDATION,
        industry=Industry.BANKING,
        target=ScenarioTarget(
            enterprise_id="bank_alpha",
            business_stream_id="payments",
            service_id="payment_service",
            component_ids=component_ids,
            environment=Environment.PRODUCTION,
        ),
        risk=RiskLevel.MEDIUM,
        initial_conditions=[
            "Payment Service is available.",
        ],
        trigger=ScenarioTrigger(
            source=SourceDomain.LOG,
            trigger_type="scope_test",
            description="Generate scope-test evidence.",
        ),
        state_sequence=[
            OperationalState.INITIALISING,
            OperationalState.OBSERVING,
            OperationalState.COMPLETED,
        ],
        behaviours=[
            ScenarioBehaviour(
                source=SourceDomain.LOG,
                during_state=OperationalState.OBSERVING,
                profile_id="scope_test",
            )
        ],
        expected_result=ExpectedScenarioResult(
            scenario_id="TEST-01",
            expected_outcome=Outcome.SUCCESSFUL,
        ),
    )


def test_declared_secondary_component_is_valid_run_scope() -> None:
    enterprise = build_enterprise()
    enterprise.components.append(
        Component(
            component_id="payment_worker",
            name="Payment Worker",
            component_type="worker",
            service_id="payment_service",
            environment=Environment.PRODUCTION,
        )
    )
    event = build_event(
        sequence_number=1,
        component="payment_worker",
    )
    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
        scenario=build_scope_scenario(
            ["payment_api", "payment_worker"]
        ),
    )
    assert report.is_valid is True
    assert report.findings == []


def test_enterprise_known_component_outside_declared_scope_is_rejected() -> None:
    enterprise = build_enterprise()
    enterprise.components.append(
        Component(
            component_id="payment_worker",
            name="Payment Worker",
            component_type="worker",
            service_id="payment_service",
            environment=Environment.PRODUCTION,
        )
    )
    event = build_event(
        sequence_number=1,
        component="payment_worker",
    )
    report = CrossSourceValidator().validate(
        events=[event],
        context=build_context(),
        enterprise=enterprise,
        scenario=build_scope_scenario(
            ["payment_api"]
        ),
    )
    assert report.is_valid is False
    assert "execution_target_scope" in {
        finding.rule
        for finding in report.findings
    }
