from synthetic_ops_generator.domain.enterprise import (
    Enterprise,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
)


class ScenarioValidationError(ValueError):
    pass


def validate_scenario_against_enterprise(
    scenario: ScenarioDefinition,
    enterprise: Enterprise,
) -> None:
    target = scenario.target

    if target.enterprise_id != enterprise.enterprise_id:
        raise ScenarioValidationError(
            f"Scenario enterprise '{target.enterprise_id}' "
            f"does not match loaded enterprise "
            f"'{enterprise.enterprise_id}'."
        )

    if scenario.industry != enterprise.industry:
        raise ScenarioValidationError(
            f"Scenario industry '{scenario.industry}' "
            f"does not match enterprise industry "
            f"'{enterprise.industry}'."
        )

    streams = {
        stream.stream_id: stream
        for stream in enterprise.business_streams
    }

    if target.business_stream_id not in streams:
        raise ScenarioValidationError(
            "Scenario references unknown business stream: "
            f"{target.business_stream_id}"
        )

    services = {
        service.service_id: service
        for service in enterprise.services
    }

    service = services.get(target.service_id)

    if service is None:
        raise ScenarioValidationError(
            "Scenario references unknown service: "
            f"{target.service_id}"
        )

    if (
        service.business_stream_id
        != target.business_stream_id
    ):
        raise ScenarioValidationError(
            f"Service '{target.service_id}' does not belong "
            f"to business stream "
            f"'{target.business_stream_id}'."
        )

    components = {
        component.component_id: component
        for component in enterprise.components
    }

    for component_id in target.component_ids:
        component = components.get(component_id)

        if component is None:
            raise ScenarioValidationError(
                "Scenario references unknown component: "
                f"{component_id}"
            )

        if component.service_id != target.service_id:
            raise ScenarioValidationError(
                f"Component '{component_id}' does not belong "
                f"to service '{target.service_id}'."
            )

        if component.environment != target.environment:
            raise ScenarioValidationError(
                f"Component '{component_id}' environment "
                f"'{component.environment}' does not match "
                f"Scenario environment "
                f"'{target.environment}'."
            )