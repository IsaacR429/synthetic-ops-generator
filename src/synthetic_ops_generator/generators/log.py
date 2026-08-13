from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.operational_log import (
    LogSeverity,
    OperationalLog,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.generators.base import SourceGenerator
from synthetic_ops_generator.scenarios.context import ScenarioContext
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
    SourceDomain,
)


@dataclass(frozen=True)
class LogDefinition:
    log_type: str
    severity: LogSeverity
    message: str
    component_scoped: bool = True
    error_code: str | None = None
    attributes: Mapping[str, Any] | None = None


DEFAULT_NORMAL_LOGS = (
    LogDefinition(
        log_type="request_accepted",
        severity=LogSeverity.INFO,
        message="Service request accepted.",
        attributes={
            "operation_status": "accepted",
        },
    ),
    LogDefinition(
        log_type="request_completed",
        severity=LogSeverity.INFO,
        message="Service request completed successfully.",
        attributes={
            "operation_status": "completed",
        },
    ),
    LogDefinition(
        log_type="service_health",
        severity=LogSeverity.INFO,
        message="Service operating normally.",
        component_scoped=False,
        attributes={
            "health_status": "normal",
        },
    ),
)


DEFAULT_DEGRADATION_LOGS = (
    LogDefinition(
        log_type="request_timeout",
        severity=LogSeverity.ERROR,
        message="Service request exceeded the expected response window.",
        error_code="REQUEST_TIMEOUT",
        attributes={
            "operation_status": "timed_out",
        },
    ),
    LogDefinition(
        log_type="dependency_error",
        severity=LogSeverity.ERROR,
        message="A downstream dependency returned an operational error.",
        error_code="DEPENDENCY_ERROR",
        attributes={
            "dependency_status": "degraded",
        },
    ),
    LogDefinition(
        log_type="service_health",
        severity=LogSeverity.WARNING,
        message="Service operating in a degraded state.",
        component_scoped=False,
        attributes={
            "health_status": "degraded",
        },
    ),
)


DEFAULT_RECOVERY_LOGS = (
    LogDefinition(
        log_type="request_completed",
        severity=LogSeverity.INFO,
        message="Service request completed successfully after recovery.",
        attributes={
            "operation_status": "completed",
        },
    ),
    LogDefinition(
        log_type="dependency_recovered",
        severity=LogSeverity.INFO,
        message="Downstream dependency has recovered.",
        attributes={
            "dependency_status": "healthy",
        },
    ),
    LogDefinition(
        log_type="service_health",
        severity=LogSeverity.INFO,
        message="Service operating normally after recovery.",
        component_scoped=False,
        attributes={
            "health_status": "recovered",
        },
    ),
)


class LogGenerator(SourceGenerator):
    """
    Generates structured synthetic operational logs.

    The generator expresses source evidence associated with
    Scenario behaviour. It does not perform RCA or infer an
    operational decision.
    """

    source_system = "synthetic_logs"

    def __init__(
        self,
        *,
        ids: IdFactory,
        behaviour: ScenarioBehaviour,
        logs: tuple[
            LogDefinition,
            ...,
        ]
        | None = None,
    ) -> None:
        if behaviour.source != SourceDomain.LOG:
            raise ValueError(
                "LogGenerator requires a Log behaviour."
            )

        if logs is not None and not logs:
            raise ValueError(
                "LogGenerator requires at least one Log definition."
            )

        self._ids = ids
        self._behaviour = behaviour
        self._logs = logs

    def _definitions_for_profile(
        self,
    ) -> tuple[LogDefinition, ...]:
        if self._logs is not None:
            return self._logs

        if (
            self._behaviour.profile_id
            == "normal_operational_logs"
        ):
            return DEFAULT_NORMAL_LOGS

        if (
            self._behaviour.profile_id
            == "degradation_error_logs"
        ):
            return DEFAULT_DEGRADATION_LOGS

        if (
            self._behaviour.profile_id
            == "recovery_operational_logs"
        ):
            return DEFAULT_RECOVERY_LOGS

        raise ValueError(
            "Unsupported Log behaviour profile: "
            f"{self._behaviour.profile_id}"
        )

    async def generate(
        self,
        context: ScenarioContext,
    ) -> AsyncIterator[GeneratedEvent]:
        if context.scenario_state != self._behaviour.during_state:
            return

        definitions = self._definitions_for_profile()

        for definition in definitions:
            component = (
                context.component
                if definition.component_scoped
                else None
            )

            operational_log = OperationalLog(
                log_id=self._ids.log_id(),
                chg_id=context.chg_id,
                log_type=definition.log_type,
                severity=definition.severity,
                message=definition.message,
                service=context.service,
                component=component,
                timestamp=context.simulation_time,
                error_code=definition.error_code,
                attributes=dict(
                    definition.attributes or {}
                ),
            )

            yield GeneratedEvent(
                event_id=self._ids.event_id(),
                event_type="log.observed",
                event_time=context.simulation_time,
                source_system=self.source_system,
                scenario_id=context.scenario_id,
                run_id=context.run_id,
                chg_id=context.chg_id,
                business_stream=context.business_stream,
                service=context.service,
                component=operational_log.component,
                environment=context.environment,
                sequence_number=context.next_sequence(),
                data={
                    "log": operational_log.model_dump(
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