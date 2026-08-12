from collections.abc import AsyncIterator
from dataclasses import dataclass

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.manual_validation import (
    ManualValidation,
    ManualValidationResult,
    ManualValidationStatus,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


@dataclass(frozen=True)
class ManualValidationDefinition:
    validation_type: str
    name: str
    mandatory: bool = True
    component_scoped: bool = False
    validated_by: str = "synthetic_operations_validator"


DEFAULT_REQUIRED_VALIDATIONS = (
    ManualValidationDefinition(
        validation_type="business_validation",
        name="Business workflow validation",
        mandatory=True,
        component_scoped=False,
    ),
    ManualValidationDefinition(
        validation_type="operational_readiness",
        name="Operational readiness validation",
        mandatory=True,
        component_scoped=True,
    ),
)


class ManualValidationGenerator(SourceGenerator):
    """
    Generates synthetic manual-validation source evidence.

    The generator owns validation lifecycle representation only.
    It does not create Evidence objects and does not calculate
    the final operational decision.
    """

    source_system = "synthetic_manual_validation"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        validations: tuple[
            ManualValidationDefinition,
            ...,
        ] = DEFAULT_REQUIRED_VALIDATIONS,
    ) -> None:
        if behaviour.source != SourceDomain.MANUAL_VALIDATION:
            raise ValueError(
                "ManualValidationGenerator requires "
                "a Manual Validation behaviour."
            )

        if not validations:
            raise ValueError(
                "ManualValidationGenerator requires "
                "at least one validation definition."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._validations = validations

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if (
            self._behaviour.profile_id
            != "all_required_validations_pass"
        ):
            raise ValueError(
                "Unsupported Manual Validation behaviour profile: "
                f"{self._behaviour.profile_id}"
            )

        for definition in self._validations:
            validation_id = self._ids.validation_id()

            component = (
                context.component
                if definition.component_scoped
                else None
            )

            requested = ManualValidation(
                validation_id=validation_id,
                chg_id=context.chg_id,
                validation_type=definition.validation_type,
                name=definition.name,
                service=context.service,
                component=component,
                mandatory=definition.mandatory,
                status=ManualValidationStatus.PENDING,
                requested_at=context.simulation_time,
            )

            yield self._event(
                context=context,
                event_type="manual_validation.requested",
                validation=requested,
            )

            completed = ManualValidation(
                validation_id=validation_id,
                chg_id=context.chg_id,
                validation_type=definition.validation_type,
                name=definition.name,
                service=context.service,
                component=component,
                mandatory=definition.mandatory,
                status=ManualValidationStatus.COMPLETED,
                result=ManualValidationResult.PASSED,
                requested_at=requested.requested_at,
                completed_at=context.simulation_time,
                validated_by=definition.validated_by,
            )

            yield self._event(
                context=context,
                event_type="manual_validation.completed",
                validation=completed,
            )

    def _event(
        self,
        *,
        context: ScenarioContext,
        event_type: str,
        validation: ManualValidation,
    ) -> GeneratedEvent:
        return GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type=event_type,
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=validation.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "validation": validation.model_dump(
                    mode="json"
                ),
                "behaviour_profile_id": (
                    self._behaviour.profile_id
                ),
                "scenario_state": (
                    context.scenario_state.value
                ),
            },
        )