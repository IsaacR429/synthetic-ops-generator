from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from synthetic_ops_generator.api.models import (
    HistoricalExecutionCapabilityResponse,
    HistoricalExecutionConfigurationResponse,
    ScenarioCapabilitiesResponse,
    ScenarioDetailResponse,
    ScenarioSummaryResponse,
)
from synthetic_ops_generator.control.configuration import (
    DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION,
)
from synthetic_ops_generator.control.models import (
    RunExecutionMode,
)
from synthetic_ops_generator.scenarios.capabilities import (
    resolve_scenario_execution_capabilities,
)
from synthetic_ops_generator.scenarios.catalogue import (
    ScenarioCatalogue,
)

router = APIRouter(
    prefix="/scenarios",
    tags=["scenarios"],
)


def get_scenario_catalogue(
    request: Request,
) -> ScenarioCatalogue:
    return request.app.state.scenario_catalogue


ScenarioCatalogueDependency = Annotated[
    ScenarioCatalogue,
    Depends(get_scenario_catalogue),
]


@router.get(
    "",
    response_model=list[ScenarioSummaryResponse],
)
async def list_scenarios(
    catalogue: ScenarioCatalogueDependency,
) -> list[ScenarioSummaryResponse]:
    scenarios = catalogue.list_scenarios()

    return [
        ScenarioSummaryResponse.from_definition(scenario)
        for scenario in scenarios
    ]


@router.get(
    "/{scenario_id}",
    response_model=ScenarioDetailResponse,
)
async def get_scenario(
    scenario_id: str,
    catalogue: ScenarioCatalogueDependency,
) -> ScenarioDetailResponse:
    scenario = catalogue.get_scenario(scenario_id)

    if scenario is None:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{scenario_id}' was not found.",
        )

    return ScenarioDetailResponse.from_definition(scenario)


@router.get(
    "/{scenario_id}/capabilities",
    response_model=ScenarioCapabilitiesResponse,
)
async def get_scenario_capabilities(
    scenario_id: str,
    catalogue: ScenarioCatalogueDependency,
) -> ScenarioCapabilitiesResponse:
    scenario = catalogue.get_scenario(
        scenario_id
    )

    if scenario is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Scenario '{scenario_id}' "
                "was not found."
            ),
        )

    capabilities = (
        resolve_scenario_execution_capabilities(
            scenario
        )
    )

    execution_modes = [
        RunExecutionMode.STANDARD
    ]

    if capabilities.historical_supported:
        execution_modes.append(
            RunExecutionMode.HISTORICAL
        )

    return ScenarioCapabilitiesResponse(
        scenario_id=scenario.scenario_id,
        execution_modes=execution_modes,
        historical=(
            HistoricalExecutionCapabilityResponse(
                supported=(
                    capabilities.historical_supported
                ),
                unavailable_reason=(
                    None
                    if capabilities.historical_supported
                    else (
                        "Managed historical execution "
                        "currently requires an incident "
                        "and rollback scenario."
                    )
                ),
                configuration=(
                    HistoricalExecutionConfigurationResponse.from_configuration(
                        DEFAULT_HISTORICAL_EXECUTION_CONFIGURATION
                    )
                    if capabilities.historical_supported
                    else None
                ),
            )
        ),
    )
