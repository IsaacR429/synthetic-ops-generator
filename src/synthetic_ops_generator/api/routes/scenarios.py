from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from synthetic_ops_generator.api.models import (
    ScenarioDetailResponse,
    ScenarioSummaryResponse,
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
