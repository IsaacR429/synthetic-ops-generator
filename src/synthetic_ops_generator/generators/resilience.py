from collections.abc import AsyncIterator
from datetime import timedelta

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import SourceDomain
from synthetic_ops_generator.domain.resilience import (
    ReplicationObservation,
    ResilienceObservation,
    ResilienceObservationType,
    ServiceAvailabilityObservation,
    ServiceAvailabilityState,
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
    REPLICATION_OBSERVED,
    SERVICE_AVAILABLE,
    SERVICE_UNAVAILABLE,
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


_AVAILABILITY_PROFILE_TO_STATE = {
    SERVICE_UNAVAILABLE: (
        ServiceAvailabilityState.UNAVAILABLE
    ),
    SERVICE_AVAILABLE: (
        ServiceAvailabilityState.AVAILABLE
    ),
}


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
        replication_target: ScenarioExecutionTarget | None = None,
    ) -> None:
        if behaviour.source != SourceDomain.RESILIENCE:
            raise ValueError(
                "ResilienceGenerator requires "
                "a Resilience behaviour."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._transition_target = transition_target
        self._replication_target = replication_target

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
        availability_state = (
            _AVAILABILITY_PROFILE_TO_STATE.get(
                profile_id
            )
        )

        is_replication_profile = (
            profile_id == REPLICATION_OBSERVED
        )

        if (
            observation_type is None
            and availability_state is None
            and not is_replication_profile
        ):
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

        elif profile_id in _AVAILABILITY_PROFILE_TO_STATE:
            if self._transition_target is not None:
                raise ValueError(
                    "Resilience availability profile "
                    "cannot use a transition target."
                )

            observation = ServiceAvailabilityObservation(
                observation_id=(
                    self._ids.resilience_observation_id()
                ),
                availability_state=availability_state,
                service=context.service,
                component=context.component,
                site_id=context.site_id,
                service_instance_id=(
                    context.service_instance_id
                ),
                observed_at=context.simulation_time,
            )

        elif is_replication_profile:
            if self._behaviour.resilience_replication is None:
                raise ValueError(
                    "Resilience replication profile requires "
                    "replication configuration."
                )

            if self._replication_target is None:
                raise ValueError(
                    "Resilience replication profile requires "
                    "a replication target."
                )

            if self._transition_target is not None:
                raise ValueError(
                    "Resilience replication profile cannot use "
                    "a transition target."
                )

            offset_seconds = (
                self._behaviour.resilience_replication
                .last_successful_replication_offset_seconds
            )

            last_successful_replication_at = (
                context.simulation_time
                - timedelta(seconds=offset_seconds)
                if offset_seconds is not None
                else None
            )

            observation = ReplicationObservation(
                observation_id=(
                    self._ids.resilience_observation_id()
                ),
                service=context.service,
                component=context.component,
                from_site_id=context.site_id,
                from_service_instance_id=(
                    context.service_instance_id
                ),
                to_site_id=self._replication_target.site_id,
                to_service_instance_id=(
                    self._replication_target
                    .service_instance_id
                ),
                replication_status=(
                    self._behaviour.resilience_replication
                    .replication_status
                ),
                last_successful_replication_at=(
                    last_successful_replication_at
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
                (
                    "service_availability_observation"
                    if profile_id
                    in _AVAILABILITY_PROFILE_TO_STATE
                    else (
                        "replication_observation"
                        if is_replication_profile
                        else "resilience_observation"
                    )
                ): (
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
