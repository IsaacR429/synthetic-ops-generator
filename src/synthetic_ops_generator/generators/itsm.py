from collections.abc import AsyncIterator
from datetime import timedelta

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.change import (
    Approval,
    ApprovalStatus,
    Change,
    ChangeStatus,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


class ITSMGenerator(SourceGenerator):
    """
    Generates synthetic ITSM evidence for a Scenario Run.

    Behaviour is selected through reusable Scenario behaviour profiles.
    The generator does not control Scenario state, time, or CHG identity.
    """

    source_system = "synthetic_itsm"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        service_owner: str,
        component_ids: list[str],
        implementation_window_seconds: int = 3600,
    ) -> None:
        if behaviour.source != SourceDomain.ITSM:
            raise ValueError(
                "ITSMGenerator requires an ITSM behaviour."
            )

        if implementation_window_seconds <= 0:
            raise ValueError(
                "Implementation window must be greater than zero."
            )

        if not service_owner:
            raise ValueError(
                "ITSMGenerator requires a service owner."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._service_owner = service_owner
        self._component_ids = list(component_ids)
        self._implementation_window_seconds = (
            implementation_window_seconds
        )

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if self._behaviour.profile_id == "approved_change":
            async for event in self._generate_approved_change(
                context
            ):
                yield event
            return

        if (
            self._behaviour.profile_id
            == "missing_required_approval"
        ):
            async for event in self._generate_missing_required_approval(
                context
            ):
                yield event
            return

        raise ValueError(
            "Unsupported ITSM behaviour profile: "
            f"{self._behaviour.profile_id}"
        )

    async def _generate_approved_change(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        change = Change(
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            components=self._component_ids,
            risk=context.risk,
            owner=self._service_owner,
            environment=context.environment,
            status=ChangeStatus.CREATED,
            implementation_window_start=context.simulation_time,
            implementation_window_end=(
                context.simulation_time
                + timedelta(
                    seconds=self._implementation_window_seconds
                )
            ),
        )

        yield GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type="itsm.change.created",
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "change": change.model_dump(mode="json"),
            },
        )

        approval = Approval(
            approval_id=self._ids.approval_id(),
            chg_id=context.chg_id,
            approval_type="implementation",
            status=ApprovalStatus.APPROVED,
            source=self.source_system,
            timestamp=context.simulation_time,
        )

        yield GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type="itsm.approval.approved",
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "approval": approval.model_dump(mode="json"),
                "change_status": ChangeStatus.APPROVED.value,
            },
        )

    async def _generate_missing_required_approval(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        change = Change(
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            components=self._component_ids,
            risk=context.risk,
            owner=self._service_owner,
            environment=context.environment,
            status=ChangeStatus.CREATED,
            implementation_window_start=context.simulation_time,
            implementation_window_end=(
                context.simulation_time
                + timedelta(
                    seconds=self._implementation_window_seconds
                )
            ),
        )

        yield GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type="itsm.change.created",
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "change": change.model_dump(mode="json"),
            },
        )

        approval = Approval(
            approval_id=self._ids.approval_id(),
            chg_id=context.chg_id,
            approval_type="implementation",
            status=ApprovalStatus.MISSING,
            source=self.source_system,
            timestamp=context.simulation_time,
        )

        yield GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type="itsm.approval.missing",
            event_time=context.simulation_time,
            source_system=self.source_system,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "approval": approval.model_dump(mode="json"),
                "change_status": ChangeStatus.CREATED.value,
            },
        )