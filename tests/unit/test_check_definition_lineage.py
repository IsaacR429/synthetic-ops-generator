from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.checks.catalogue import (
    APPLICATION_FUNCTIONAL_VALIDATION,
    INFRASTRUCTURE_CONNECTIVITY,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    OperationalState,
    RiskLevel,
    SourceDomain,
)
from synthetic_ops_generator.domain.operational_test import (
    OperationalTest,
    TestCategory as Category,
    TestExecutionStatus as ExecutionStatus,
)
from synthetic_ops_generator.events.envelope import (
    GeneratedEvent,
)
from synthetic_ops_generator.generators.application_test import (
    ApplicationTestGenerator,
)
from synthetic_ops_generator.generators.infrastructure_test import (
    InfrastructureTestGenerator,
)
from synthetic_ops_generator.reporting.csv_export import (
    RUN_EVIDENCE_CSV_COLUMNS,
)
from synthetic_ops_generator.reporting.evidence_row import (
    project_run_evidence_row,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
)


def _context() -> ScenarioContext:
    return ScenarioContext(
        scenario_id="INS-P1C",
        run_id="RUN-P1C-001",
        chg_id="CHG-P1C-001",
        business_stream="claims",
        service="claims_service",
        component="claims_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.HIGH,
        scenario_state=OperationalState.OBSERVING,
        simulation_time=datetime(
            2026,
            10,
            18,
            1,
            30,
            tzinfo=UTC,
        ),
        random_seed=42,
    )


async def _collect(generator, context):
    events = []

    async for event in generator.generate(context):
        events.append(event)

    return events


def _application_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id="p1c_application_lineage",
        source=SourceDomain.APPLICATION_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="all_mandatory_tests_pass",
    )


def _infrastructure_behaviour() -> ScenarioBehaviour:
    return ScenarioBehaviour(
        behaviour_id="p1c_infrastructure_lineage",
        source=SourceDomain.INFRASTRUCTURE_TEST,
        during_state=OperationalState.OBSERVING,
        profile_id="all_required_checks_pass",
    )


def test_operational_test_requires_check_definition_identity() -> None:
    with pytest.raises(ValidationError):
        OperationalTest(
            test_id="TST-P1C-001",
            chg_id="CHG-P1C-001",
            category=Category.APPLICATION,
            test_type="functional_validation",
            name="Service functional validation",
            service="claims_service",
            component="claims_api",
            mandatory=True,
            status=ExecutionStatus.PLANNED,
            planned_at=datetime(
                2026,
                10,
                18,
                1,
                30,
                tzinfo=UTC,
            ),
        )


def test_operational_test_preserves_check_definition_identity() -> None:
    operational_test = OperationalTest(
        test_id="TST-P1C-002",
        check_definition_id=(
            "application.functional_validation"
        ),
        chg_id="CHG-P1C-001",
        category=Category.APPLICATION,
        test_type="functional_validation",
        name="Service functional validation",
        service="claims_service",
        component="claims_api",
        mandatory=True,
        status=ExecutionStatus.PLANNED,
        planned_at=datetime(
            2026,
            10,
            18,
            1,
            30,
            tzinfo=UTC,
        ),
    )

    assert (
        operational_test.check_definition_id
        == "application.functional_validation"
    )

    assert (
        operational_test.model_dump()["check_definition_id"]
        == "application.functional_validation"
    )


def test_application_generator_emits_definition_identity() -> None:
    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=_application_behaviour(),
    )

    events = asyncio.run(
        _collect(
            generator,
            _context(),
        )
    )

    matching = [
        event
        for event in events
        if (
            event.data["test"]["test_type"]
            == "functional_validation"
        )
    ]

    assert len(matching) == 2

    assert {
        event.data["test"]["check_definition_id"]
        for event in matching
    } == {
        APPLICATION_FUNCTIONAL_VALIDATION.check_definition_id
    }


def test_infrastructure_generator_emits_definition_identity() -> None:
    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=_infrastructure_behaviour(),
    )

    events = asyncio.run(
        _collect(
            generator,
            _context(),
        )
    )

    matching = [
        event
        for event in events
        if event.data["test"]["test_type"] == "connectivity"
    ]

    assert len(matching) == 2

    assert {
        event.data["test"]["check_definition_id"]
        for event in matching
    } == {
        INFRASTRUCTURE_CONNECTIVITY.check_definition_id
    }


def test_run_evidence_projects_executed_check_identity() -> None:
    generator = ApplicationTestGenerator(
        ids=IdFactory(),
        behaviour=_application_behaviour(),
    )

    events = asyncio.run(
        _collect(
            generator,
            _context(),
        )
    )

    executed = next(
        event
        for event in events
        if (
            event.event_type == "application_test.passed"
            and event.data["test"]["test_type"]
            == "functional_validation"
        )
    )

    row = project_run_evidence_row(executed)

    assert (
        row.check_definition_id
        == APPLICATION_FUNCTIONAL_VALIDATION.check_definition_id
    )
    assert (
        row.operational_test_id
        == executed.data["test"]["test_id"]
    )
    assert row.operational_test_category == "application"
    assert (
        row.operational_test_type
        == "functional_validation"
    )
    assert row.operational_test_status == "executed"
    assert row.operational_test_result == "passed"


def test_run_evidence_projects_planned_check_without_result() -> None:
    generator = InfrastructureTestGenerator(
        ids=IdFactory(),
        behaviour=_infrastructure_behaviour(),
    )

    events = asyncio.run(
        _collect(
            generator,
            _context(),
        )
    )

    planned = next(
        event
        for event in events
        if (
            event.event_type
            == "infrastructure_test.planned"
            and event.data["test"]["test_type"]
            == "connectivity"
        )
    )

    row = project_run_evidence_row(planned)

    assert (
        row.check_definition_id
        == INFRASTRUCTURE_CONNECTIVITY.check_definition_id
    )
    assert row.operational_test_status == "planned"
    assert row.operational_test_result is None


def test_non_test_evidence_has_no_operational_test_projection() -> None:
    event = GeneratedEvent(
        event_id="evt-p1c-metric",
        event_type="metric.observed",
        event_time=datetime(
            2026,
            10,
            18,
            1,
            31,
            tzinfo=UTC,
        ),
        source_system="synthetic_observability",
        source_domain=SourceDomain.METRIC,
        scenario_id="INS-P1C",
        run_id="RUN-P1C-001",
        behaviour_id="p1c_metric",
        chg_id="CHG-P1C-001",
        business_stream="claims",
        service="claims_service",
        component=None,
        environment=Environment.PRODUCTION,
        sequence_number=1,
        synthetic=True,
        data={},
    )

    row = project_run_evidence_row(event)

    assert row.check_definition_id is None
    assert row.operational_test_id is None
    assert row.operational_test_category is None
    assert row.operational_test_type is None
    assert row.operational_test_status is None
    assert row.operational_test_result is None


def test_csv_contract_exposes_stable_check_lineage() -> None:
    synthetic_index = (
        RUN_EVIDENCE_CSV_COLUMNS.index("synthetic")
    )

    assert RUN_EVIDENCE_CSV_COLUMNS[
        synthetic_index + 1:
        synthetic_index + 7
    ] == (
        "check_definition_id",
        "operational_test_id",
        "operational_test_category",
        "operational_test_type",
        "operational_test_status",
        "operational_test_result",
    )


def test_reporting_does_not_promote_execution_mandatory_to_policy_truth() -> None:
    from synthetic_ops_generator.reporting.evidence_row import (
        RunEvidenceRow,
    )

    assert (
        "operational_test_mandatory"
        not in RunEvidenceRow.__dataclass_fields__
    )
