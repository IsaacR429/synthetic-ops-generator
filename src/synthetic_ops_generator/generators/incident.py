from collections.abc import AsyncIterator
from dataclasses import dataclass

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


@dataclass(frozen=True)
class IncidentDefinition:
    title: str
    severity: IncidentSeverity
    description: str | None = None
    component_scoped: bool = True
    link_to_change: bool = True


DEFAULT_CHANGE_INCIDENT = IncidentDefinition(
    title="Post-change service degradation",
    description=(
        "Operational degradation detected during "
        "the post-change observation window."
    ),
    severity=IncidentSeverity.HIGH,
    component_scoped=True,
    link_to_change=True,
)


class IncidentGenerator(SourceGenerator):
    """
    Generates synthetic ITSM Incident source records.

    The generator represents Incident facts only. It does not
    determine root cause, Change attribution, operational
    Decision or recommended Action.
    """

    source_system = "synthetic_itsm"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        incident: IncidentDefinition = DEFAULT_CHANGE_INCIDENT,
    ) -> None:
        if behaviour.source != SourceDomain.INCIDENT:
            raise ValueError(
                "IncidentGenerator requires "
                "an Incident behaviour."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._incident = incident

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if self._behaviour.profile_id == "no_incident":
            return

        if self._behaviour.profile_id != "incident_created":
            raise ValueError(
                "Unsupported Incident behaviour profile: "
                f"{self._behaviour.profile_id}"
            )

        incident_id = self._ids.incident_id()

        component = (
            context.component
            if self._incident.component_scoped
            else None
        )

        chg_id = (
            context.chg_id
            if self._incident.link_to_change
            else None
        )

        incident = Incident(
            incident_id=incident_id,
            chg_id=chg_id,
            title=self._incident.title,
            description=self._incident.description,
            severity=self._incident.severity,
            status=IncidentStatus.OPEN,
            service=context.service,
            component=component,
            created_at=context.simulation_time,
        )

        context.incident_id = incident_id

        yield GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type="itsm.incident.created",
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=incident.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=incident.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "incident": incident.model_dump(
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