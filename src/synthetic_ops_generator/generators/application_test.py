from collections.abc import AsyncIterator
from synthetic_ops_generator.checks.catalogue import (
    DEFAULT_APPLICATION_CHECKS,
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
    ALL_MANDATORY_TESTS_PASS,
    MANDATORY_TEST_REGRESSION,
)




class ApplicationTestGenerator(SourceGenerator):
    """
    Generates synthetic application-validation evidence.

    The generator expresses reusable application-test behaviour.
    It does not control Scenario state, simulation time, or CHG identity.
    """

    source_system = "synthetic_application_test"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        tests: tuple[CheckExecutionSpec, ...] = DEFAULT_APPLICATION_CHECKS,
    ) -> None:
        if behaviour.source != SourceDomain.APPLICATION_TEST:
            raise ValueError(
                "ApplicationTestGenerator requires "
                "an application-test behaviour."
            )

        if not tests:
            raise ValueError(
                "ApplicationTestGenerator requires "
                "at least one test definition."
            )

        if any(
            spec.definition.category
            != TestCategory.APPLICATION
            for spec in tests
        ):
            raise ValueError(
                "ApplicationTestGenerator requires "
                "application CheckDefinitions."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._tests = tests

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if (
            self._behaviour.profile_id
            == ALL_MANDATORY_TESTS_PASS
        ):
            async for event in self._generate_all_tests_pass(
                context
            ):
                yield event

            return

        if (
            self._behaviour.profile_id
            == MANDATORY_TEST_REGRESSION
        ):
            async for event in (
                self._generate_mandatory_test_regression(
                    context
                )
            ):
                yield event

            return

        raise ValueError(
            "Unsupported Application Test behaviour profile: "
            f"{self._behaviour.profile_id}"
        )

    async def _generate_all_tests_pass(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        for spec in self._tests:
            definition = spec.definition
            test_id = self._ids.test_id()

            planned = OperationalTest(
                test_id=test_id,
                check_definition_id=definition.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.APPLICATION,
                test_type=definition.test_type,
                name=definition.name,
                service=context.service,
                component=context.component,
                mandatory=spec.mandatory,
                status=TestExecutionStatus.PLANNED,
                planned_at=context.simulation_time,
            )

            yield self._event(
                context=context,
                event_type="application_test.planned",
                operational_test=planned,
            )

            executed = OperationalTest(
                test_id=test_id,
                check_definition_id=definition.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.APPLICATION,
                test_type=definition.test_type,
                name=definition.name,
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
                event_type="application_test.passed",
                operational_test=executed,
            )

    async def _generate_mandatory_test_regression(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.chg_id is None:
            raise ValueError(
                "Mandatory Test regression requires "
                "change correlation."
            )

        mandatory_specs = [
            spec
            for spec in self._tests
            if spec.mandatory
        ]

        if not mandatory_specs:
            raise ValueError(
                "Mandatory Test regression requires "
                "at least one mandatory Test."
            )

        regression_test_type = (
            mandatory_specs[-1]
            .definition.test_type
        )

        for spec in self._tests:
            definition = spec.definition
            test_id = self._ids.test_id()

            planned = OperationalTest(
                test_id=test_id,
                check_definition_id=definition.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.APPLICATION,
                test_type=definition.test_type,
                name=definition.name,
                service=context.service,
                component=context.component,
                mandatory=spec.mandatory,
                status=TestExecutionStatus.PLANNED,
                planned_at=context.simulation_time,
            )

            yield self._event(
                context=context,
                event_type="application_test.planned",
                operational_test=planned,
            )

            regression_detected = (
                definition.test_type
                == regression_test_type
            )

            executed = OperationalTest(
                test_id=test_id,
                check_definition_id=definition.check_definition_id,
                chg_id=context.chg_id,
                category=TestCategory.APPLICATION,
                test_type=definition.test_type,
                name=definition.name,
                service=context.service,
                component=context.component,
                mandatory=spec.mandatory,
                status=TestExecutionStatus.EXECUTED,
                result=(
                    TestResult.FAILED
                    if regression_detected
                    else TestResult.PASSED
                ),
                planned_at=planned.planned_at,
                executed_at=context.simulation_time,
                failure_reason=(
                    "Post-change application regression detected."
                    if regression_detected
                    else None
                ),
            )

            yield self._event(
                context=context,
                event_type=(
                    "application_test.failed"
                    if regression_detected
                    else "application_test.passed"
                ),
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