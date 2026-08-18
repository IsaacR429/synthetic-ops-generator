from collections.abc import AsyncIterator
from dataclasses import dataclass

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


@dataclass(frozen=True)
class InfrastructureCheckDefinition:
    test_type: str
    name: str
    mandatory: bool = True


DEFAULT_REQUIRED_CHECKS = (
    InfrastructureCheckDefinition(
        test_type="connectivity",
        name="Service connectivity validation",
    ),
    InfrastructureCheckDefinition(
        test_type="service_health",
        name="Service health validation",
    ),
    InfrastructureCheckDefinition(
        test_type="dependency_connectivity",
        name="Dependency connectivity validation",
    ),
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
        checks: tuple[
            InfrastructureCheckDefinition,
            ...,
        ] = DEFAULT_REQUIRED_CHECKS,
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
            == "all_required_checks_pass"
        ):
            async for event in self._generate_all_checks_pass(
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
        for check in self._checks:
            test_id = self._ids.test_id()

            planned = OperationalTest(
                test_id=test_id,
                chg_id=context.chg_id,
                category=TestCategory.INFRASTRUCTURE,
                test_type=check.test_type,
                name=check.name,
                service=context.service,
                component=context.component,
                mandatory=check.mandatory,
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
                chg_id=context.chg_id,
                category=TestCategory.INFRASTRUCTURE,
                test_type=check.test_type,
                name=check.name,
                service=context.service,
                component=context.component,
                mandatory=check.mandatory,
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
            sequence_number=context.next_sequence(),
            data={
                "test": operational_test.model_dump(
                    mode="json"
                ),
            },
        )