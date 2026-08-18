from collections.abc import AsyncIterator

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.deployment import (
    Deployment,
    DeploymentOutcome,
    DeploymentStatus,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


class DeploymentGenerator(SourceGenerator):
    """
    Generates synthetic Deployment evidence for a Scenario Run.

    Behaviour is selected through reusable Scenario behaviour profiles.
    The generator does not control Scenario state, time, or CHG identity.
    """

    source_system = "synthetic_deployment"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        artifact: str,
        artifact_version: str,
    ) -> None:
        if behaviour.source != SourceDomain.DEPLOYMENT:
            raise ValueError(
                "DeploymentGenerator requires a deployment behaviour."
            )

        if not artifact:
            raise ValueError(
                "DeploymentGenerator requires an artifact name."
            )

        if not artifact_version:
            raise ValueError(
                "DeploymentGenerator requires an artifact version."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._artifact = artifact
        self._artifact_version = artifact_version

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        if self._behaviour.profile_id == "successful_deployment":
            async for event in self._generate_successful_deployment(
                context
            ):
                yield event
            return

        if self._behaviour.profile_id == "successful_rollback":
            async for event in self._generate_successful_rollback(
                context
            ):
                yield event
            return

        raise ValueError(
            "Unsupported Deployment behaviour profile: "
            f"{self._behaviour.profile_id}"
        )

    async def _generate_successful_deployment(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        deployment_id = (
            context.deployment_id
            or self._ids.deployment_id()
        )

        context.deployment_id = deployment_id

        created = Deployment(
            deployment_id=deployment_id,
            chg_id=context.chg_id,
            artifact=self._artifact,
            artifact_version=self._artifact_version,
            service=context.service,
            component=context.component,
            status=DeploymentStatus.CREATED,
        )

        yield self._event(
            context=context,
            event_type="cicd.deployment.created",
            deployment=created,
        )

        start_time = context.simulation_time

        started = Deployment(
            deployment_id=deployment_id,
            chg_id=context.chg_id,
            artifact=self._artifact,
            artifact_version=self._artifact_version,
            service=context.service,
            component=context.component,
            start_time=start_time,
            status=DeploymentStatus.IN_PROGRESS,
        )

        yield self._event(
            context=context,
            event_type="cicd.deployment.started",
            deployment=started,
        )

        completion_time = context.simulation_time

        completed = Deployment(
            deployment_id=deployment_id,
            chg_id=context.chg_id,
            artifact=self._artifact,
            artifact_version=self._artifact_version,
            service=context.service,
            component=context.component,
            start_time=start_time,
            completion_time=completion_time,
            status=DeploymentStatus.COMPLETED,
            outcome=DeploymentOutcome.SUCCESSFUL,
        )

        yield self._event(
            context=context,
            event_type="cicd.deployment.completed",
            deployment=completed,
        )

    async def _generate_successful_rollback(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.deployment_id is None:
            raise ValueError(
                "Rollback requires an existing Deployment ID."
            )

        deployment_id = context.deployment_id
        rollback_start_time = context.simulation_time

        rollback_started = Deployment(
            deployment_id=deployment_id,
            chg_id=context.chg_id,
            artifact=self._artifact,
            artifact_version=self._artifact_version,
            service=context.service,
            component=context.component,
            start_time=rollback_start_time,
            status=DeploymentStatus.ROLLBACK,
        )

        yield self._event(
            context=context,
            event_type="cicd.deployment.rollback_started",
            deployment=rollback_started,
        )

        rollback_completion_time = context.simulation_time

        rolled_back = Deployment(
            deployment_id=deployment_id,
            chg_id=context.chg_id,
            artifact=self._artifact,
            artifact_version=self._artifact_version,
            service=context.service,
            component=context.component,
            start_time=rollback_start_time,
            completion_time=rollback_completion_time,
            status=DeploymentStatus.ROLLED_BACK,
            outcome=DeploymentOutcome.ROLLED_BACK,
        )

        yield self._event(
            context=context,
            event_type="cicd.deployment.rollback_completed",
            deployment=rolled_back,
        )

    def _event(
        self,
        *,
        context: ScenarioContext,
        event_type: str,
        deployment: Deployment,
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
            component=context.component,
            environment=context.environment,
            sequence_number=context.next_sequence(),
            data={
                "deployment": deployment.model_dump(mode="json"),
            },
        )
