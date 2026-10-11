from collections.abc import AsyncIterator

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.domain.resilience import (
    ResilienceObservation,
    ResilienceObservationType,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import (
    ScenarioContext,
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
)
from synthetic_ops_generator.scenarios.profile_contracts import (
    FAILOVER_INITIATED,
    INSTANCE_ACTIVATED,
    INSTANCE_SERVING,
    TRAFFIC_SWITCH_COMPLETED,
    TRAFFIC_SWITCH_STARTED,
)


_PROFILE_TO_OBSERVATION_TYPE = {
    FAILOVER_INITIATED: (
        ResilienceObservationType.FAILOVER_INITIATED
    ),
    TRAFFIC_SWITCH_STARTED: (
        ResilienceObservationType.TRAFFIC_SWITCH_STARTED
    ),
    TRAFFIC_SWITCH_COMPLETED: (
        ResilienceObservationType.TRAFFIC_SWITCH_COMPLETED
    ),
    INSTANCE_ACTIVATED: (
        ResilienceObservationType.INSTANCE_ACTIVATED
    ),
    INSTANCE_SERVING: (
        ResilienceObservationType.INSTANCE_SERVING
    ),
}

_TRANSITION_PROFILES = frozenset(
    {
        FAILOVER_INITIATED,
        TRAFFIC_SWITCH_STARTED,
        TRAFFIC_SWITCH_COMPLETED,
    }
)

_INSTANCE_STATE_PROFILES = frozenset(
    {
        INSTANCE_ACTIVATED,
        INSTANCE_SERVING,
    }
)


class ResilienceGenerator(SourceGenerator):
    """
    Generate factual resilience-control observations.

    The generator records observed transition and instance-state
    facts only. It does not determine DR success, RTO compliance,
    resilience adequacy or residual risk.
    """

    source_system = "synthetic_resilience"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        transition_target: ScenarioExecutionTarget | None = None,
    ) -> None:
        if behaviour.source != SourceDomain.RESILIENCE:
            raise ValueError(
                "ResilienceGenerator requires "
                "a Resilience behaviour."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._transition_target = transition_target

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        profile_id = self._behaviour.profile_id

        observation_type = _PROFILE_TO_OBSERVATION_TYPE.get(
            profile_id
        )

        if observation_type is None:
            raise ValueError(
                "Unsupported Resilience behaviour profile: "
                f"{profile_id}"
            )

        if profile_id in _TRANSITION_PROFILES:
            if self._transition_target is None:
                raise ValueError(
                    "Resilience transition profile requires "
                    "a transition target."
                )

            observation = ResilienceObservation(
                observation_id=(
                    self._ids.resilience_observation_id()
                ),
                observation_type=observation_type,
                service=context.service,
                component=context.component,
                from_site_id=context.site_id,
                from_service_instance_id=(
                    context.service_instance_id
                ),
                to_site_id=self._transition_target.site_id,
                to_service_instance_id=(
                    self._transition_target
                    .service_instance_id
                ),
                observed_at=context.simulation_time,
            )

        elif profile_id in _INSTANCE_STATE_PROFILES:
            if self._transition_target is not None:
                raise ValueError(
                    "Instance-state Resilience profile "
                    "cannot use a transition target."
                )

            observation = ResilienceObservation(
                observation_id=(
                    self._ids.resilience_observation_id()
                ),
                observation_type=observation_type,
                service=context.service,
                component=context.component,
                to_site_id=context.site_id,
                to_service_instance_id=(
                    context.service_instance_id
                ),
                observed_at=context.simulation_time,
            )

        else:
            raise ValueError(
                "Unsupported Resilience behaviour profile: "
                f"{profile_id}"
            )

        yield GeneratedEvent(
            event_id=self._ids.event_id(),
            event_type=f"resilience.{profile_id}",
            event_time=context.simulation_time,
            source_system=self.source_system,
            source_domain=self._behaviour.source,
            scenario_id=context.scenario_id,
            run_id=context.run_id,
            chg_id=context.chg_id,
            business_stream=context.business_stream,
            service=context.service,
            component=context.component,
            environment=context.environment,
            site_id=context.site_id,
            service_instance_id=context.service_instance_id,
            sequence_number=context.next_sequence(),
            data={
                "resilience_observation": (
                    observation.model_dump(
                        mode="json"
                    )
                ),
                "behaviour_profile_id": profile_id,
                "scenario_state": (
                    context.scenario_state.value
                ),
            },
        )
