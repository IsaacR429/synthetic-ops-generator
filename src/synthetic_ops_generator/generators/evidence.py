from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import OperationalState
from synthetic_ops_generator.domain.evidence import Evidence
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


@dataclass(frozen=True)
class EvidenceDefinition:
    evidence_type: str
    title: str
    event_types: tuple[str, ...]
    source_state: OperationalState | None = None
    component_scoped: bool = False


DEFAULT_COMPLETE_VALIDATION_EVIDENCE = (
    EvidenceDefinition(
        evidence_type="change_approval",
        title="Approved Change evidence",
        event_types=("itsm.approval.approved",),
    ),
    EvidenceDefinition(
        evidence_type="infrastructure_validation",
        title="Infrastructure validation evidence",
        event_types=("infrastructure_test.passed",),
    ),
    EvidenceDefinition(
        evidence_type="deployment_result",
        title="Deployment result evidence",
        event_types=("cicd.deployment.completed",),
    ),
    EvidenceDefinition(
        evidence_type="application_validation",
        title="Application validation evidence",
        event_types=("application_test.passed",),
    ),
    EvidenceDefinition(
        evidence_type="pre_change_baseline",
        title="Pre-change Metric baseline evidence",
        event_types=("metric.observed",),
        source_state=OperationalState.NORMAL,
    ),
    EvidenceDefinition(
        evidence_type="post_change_observation",
        title="Post-change Metric observation evidence",
        event_types=("metric.observed",),
        source_state=OperationalState.OBSERVING,
    ),
)

DEFAULT_ROLLBACK_VALIDATION_EVIDENCE = (
    EvidenceDefinition(
        evidence_type="change_approval",
        title="Approved Change evidence",
        event_types=("itsm.approval.approved",),
    ),
    EvidenceDefinition(
        evidence_type="infrastructure_validation",
        title="Infrastructure validation evidence",
        event_types=("infrastructure_test.passed",),
    ),
    EvidenceDefinition(
        evidence_type="deployment_result",
        title="Deployment result evidence",
        event_types=("cicd.deployment.completed",),
    ),
    EvidenceDefinition(
        evidence_type="application_regression",
        title="Application regression evidence",
        event_types=("application_test.failed",),
    ),
    EvidenceDefinition(
        evidence_type="degraded_observation",
        title="Post-change degradation evidence",
        event_types=(
            "metric.observed",
            "log.observed",
        ),
        source_state=OperationalState.DEGRADED,
    ),
    EvidenceDefinition(
        evidence_type="incident_record",
        title="Operational Incident evidence",
        event_types=("itsm.incident.created",),
    ),
    EvidenceDefinition(
        evidence_type="rollback_result",
        title="Deployment rollback evidence",
        event_types=(
            "cicd.deployment.rollback_completed",
        ),
    ),
    EvidenceDefinition(
        evidence_type="recovery_observation",
        title="Post-rollback recovery evidence",
        event_types=(
            "metric.observed",
            "log.observed",
        ),
        source_state=OperationalState.RECOVERY,
    ),
    EvidenceDefinition(
        evidence_type="incident_resolution",
        title="Incident resolution evidence",
        event_types=("itsm.incident.resolved",),
    ),
)


class EvidenceGenerator(SourceGenerator):
    """
    Generates structured Evidence from source events that
    already exist in the current Scenario Run.

    Evidence does not calculate a Decision, Action, RCA or
    other downstream platform conclusion.
    """

    source_system = "synthetic_evidence"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        event_history: Sequence[GeneratedEvent],
        definitions: tuple[
            EvidenceDefinition,
            ...,
        ]
        | None = None,
    ) -> None:
        if behaviour.source != SourceDomain.EVIDENCE:
            raise ValueError(
                "EvidenceGenerator requires "
                "an Evidence behaviour."
            )

        if definitions is not None and not definitions:
            raise ValueError(
                "EvidenceGenerator requires "
                "at least one Evidence definition."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._event_history = event_history
        self._definitions = definitions

    def _definitions_for_profile(
        self,
    ) -> tuple[EvidenceDefinition, ...]:
        if self._definitions is not None:
            return self._definitions

        if (
            self._behaviour.profile_id
            == "complete_validation_evidence"
        ):
            return DEFAULT_COMPLETE_VALIDATION_EVIDENCE

        if (
            self._behaviour.profile_id
            == "rollback_validation_evidence"
        ):
            return DEFAULT_ROLLBACK_VALIDATION_EVIDENCE

        raise ValueError(
            "Unsupported Evidence behaviour profile: "
            f"{self._behaviour.profile_id}"
        )

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        definitions = self._definitions_for_profile()

        history = tuple(
            event
            for event in self._event_history
            if event.scenario_id == context.scenario_id
            and event.run_id == context.run_id
            and event.chg_id == context.chg_id
        )

        for definition in definitions:
            source_events = self._select_source_events(
                history=history,
                definition=definition,
            )

            if not source_events:
                raise ValueError(
                    "Missing source events for Evidence type: "
                    f"{definition.evidence_type}"
                )

            component = (
                context.component
                if definition.component_scoped
                else None
            )

            evidence = Evidence(
                evidence_id=self._ids.evidence_id(),
                chg_id=context.chg_id,
                evidence_type=definition.evidence_type,
                title=definition.title,
                service=context.service,
                component=component,
                captured_at=context.simulation_time,
                source_event_ids=tuple(
                    event.event_id
                    for event in source_events
                ),
            )

            yield GeneratedEvent(
                event_id=self._ids.event_id(),
                event_type="evidence.captured",
                event_time=context.simulation_time,
                source_system=self.source_system,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=evidence.component,
                environment=context.environment,
                sequence_number=context.next_sequence(),
                data={
                    "evidence": evidence.model_dump(
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

    @staticmethod
    def _event_scenario_state(
        event: GeneratedEvent,
    ) -> str | None:
        direct_state = event.data.get("scenario_state")

        if isinstance(direct_state, str):
            return direct_state

        for value in event.data.values():
            if not isinstance(value, dict):
                continue

            nested_state = value.get("scenario_state")

            if isinstance(nested_state, str):
                return nested_state

        return None

    @staticmethod
    def _select_source_events(
        *,
        history: Sequence[GeneratedEvent],
        definition: EvidenceDefinition,
    ) -> tuple[GeneratedEvent, ...]:
        selected = []

        for event in history:
            if event.event_type not in definition.event_types:
                continue

            if (
                definition.source_state is not None
                and EvidenceGenerator._event_scenario_state(
                    event
                )
                != definition.source_state.value
            ):
                continue

            selected.append(event)

        return tuple(selected)