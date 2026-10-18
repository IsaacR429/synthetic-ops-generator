from collections.abc import AsyncIterator
from synthetic_ops_generator.checks.catalogue import (
    DEFAULT_INFRASTRUCTURE_CHECKS,
)
from synthetic_ops_generator.checks.models import (
    CheckExecutionSpec,
)
from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.operational_test import (
    OperationalTest,
    TestCategory,
    TestExecutionStatus,
    TestResult,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    ALL_REQUIRED_CHECKS_PASS,
    REQUIRED_CHECK_FAILED,
)




class InfrastructureTestGenerator(SourceGenerator):
    """
    Generates synthetic infrastructure-validation evidence.

    The generator expresses reusable infrastructure-test behaviour.
    It does not control Scenario state, simulation time, or CHG identity.
    """

    source_system = "synthetic_infrastructure_test"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        checks: tuple[CheckExecutionSpec, ...] = DEFAULT_INFRASTRUCTURE_CHECKS,
    ) -> None:
        if behaviour.source != SourceDomain.INFRASTRUCTURE_TEST:
            raise ValueError(
                "InfrastructureTestGenerator requires "
                "an infrastructure-test behaviour."
            )

        if not checks:
            raise ValueError(
                "InfrastructureTestGenerator requires "
                "at least one check."
            )

        if any(
            spec.definition.category
            != TestCategory.INFRASTRUCTURE
            for spec in checks
        ):
            raise ValueError(
                "InfrastructureTestGenerator requires "
                "infrastructure CheckDefinitions."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._checks = checks

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if (
            self._behaviour.profile_id
            == ALL_REQUIRED_CHECKS_PASS
        ):
            async for event in self._generate_all_checks_pass(
                context
            ):
                yield event
            return

        if (
            self._behaviour.profile_id
            == REQUIRED_CHECK_FAILED
        ):
            async for event in self._generate_required_check_failed(
                context
            ):
                yield event
            return

        raise ValueError(
            "Unsupported Infrastructure Test behaviour profile: "
            f"{self._behaviour.profile_id}"
        )

    async def _generate_all_checks_pass(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        for spec in self._checks:
            check = spec.definition
            test_id = self._ids.test_id()

            planned = OperationalTest(
                test_id=test_id,
                check_definition_id=check.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.INFRASTRUCTURE,
                test_type=check.test_type,
                name=check.name,
                service=context.service,
                component=context.component,
                mandatory=spec.mandatory,
                status=TestExecutionStatus.PLANNED,
                planned_at=context.simulation_time,
            )

            yield self._event(
                context=context,
                event_type="infrastructure_test.planned",
                operational_test=planned,
            )

            executed = OperationalTest(
                test_id=test_id,
                check_definition_id=check.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.INFRASTRUCTURE,
                test_type=check.test_type,
                name=check.name,
                service=context.service,
                component=context.component,
                mandatory=spec.mandatory,
                status=TestExecutionStatus.EXECUTED,
                result=TestResult.PASSED,
                planned_at=planned.planned_at,
                executed_at=context.simulation_time,
            )

            yield self._event(
                context=context,
                event_type="infrastructure_test.passed",
                operational_test=executed,
            )

    async def _generate_required_check_failed(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if not any(spec.mandatory for spec in self._checks):
            raise ValueError(
                "required_check_failed requires at least "
                "one mandatory infrastructure check."
            )

        failure_emitted = False

        for spec in self._checks:
            check = spec.definition
            test_id = self._ids.test_id()

            planned = OperationalTest(
                test_id=test_id,
                check_definition_id=check.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.INFRASTRUCTURE,
                test_type=check.test_type,
                name=check.name,
                service=context.service,
                component=context.component,
                mandatory=spec.mandatory,
                status=TestExecutionStatus.PLANNED,
                planned_at=context.simulation_time,
            )

            yield self._event(
                context=context,
                event_type="infrastructure_test.planned",
                operational_test=planned,
            )

            should_fail = (
                spec.mandatory
                and not failure_emitted
            )

            if should_fail:
                executed = OperationalTest(
                    test_id=test_id,
                    check_definition_id=check.check_definition_id,
                    chg_id=context.chg_id,
                    category=TestCategory.INFRASTRUCTURE,
                    test_type=check.test_type,
                    name=check.name,
                    service=context.service,
                    component=context.component,
                    mandatory=spec.mandatory,
                    status=TestExecutionStatus.EXECUTED,
                    result=TestResult.FAILED,
                    planned_at=planned.planned_at,
                    executed_at=context.simulation_time,
                    failure_reason=(
                        "Required infrastructure check failed."
                    ),
                )

                failure_emitted = True
                event_type = "infrastructure_test.failed"
            else:
                executed = OperationalTest(
                    test_id=test_id,
                    check_definition_id=check.check_definition_id,
                    chg_id=context.chg_id,
                    category=TestCategory.INFRASTRUCTURE,
                    test_type=check.test_type,
                    name=check.name,
                    service=context.service,
                    component=context.component,
                    mandatory=spec.mandatory,
                    status=TestExecutionStatus.EXECUTED,
                    result=TestResult.PASSED,
                    planned_at=planned.planned_at,
                    executed_at=context.simulation_time,
                )

                event_type = "infrastructure_test.passed"

            yield self._event(
                context=context,
                event_type=event_type,
                operational_test=executed,
            )

    def _event(
        self,
        *,
        context: ScenarioContext,
        event_type: str,
        operational_test: OperationalTest,
    ) -> GeneratedEvent:
        return GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type=event_type,
            event_time=context.simulation_time,
            source_system=self.source_system,
            source_domain=self._behaviour.source,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=operational_test.component,
            environment=context.environment,
            site_id=context.site_id,
            service_instance_id=context.service_instance_id,
            sequence_number=context.next_sequence(),
            data={
                "test": operational_test.model_dump(
                    mode="json"
                ),
            },
        )