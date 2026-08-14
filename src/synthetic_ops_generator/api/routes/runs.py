from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from synthetic_ops_generator.api.models import (
    ReplayRunResponse,
    RunResponse,
    StartRunRequest,
    StartRunResponse,
    StopRunResponse,
)
from synthetic_ops_generator.control.service import (
    ControlService,
    RunNotFoundError,
    RunNotReplayableError,
    RunNotStoppableError,
    ScenarioNotFoundError,
)

router = APIRouter(
    prefix="/runs",
    tags=["runs"],
)


def get_control_service(
    request: Request,
) -> ControlService:
    return request.app.state.control_service


ControlServiceDependency = Annotated[
    ControlService,
    Depends(get_control_service),
]


@router.post(
    "",
    response_model=StartRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(
    request: StartRunRequest,
    service: ControlServiceDependency,
) -> StartRunResponse:
    try:
        result = await service.start_run(
            scenario_id=request.scenario_id,
            random_seed=request.random_seed,
            execution_mode=(
                request.execution_mode
            ),
        )
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return StartRunResponse.from_result(
        result
    )


@router.get(
    "/{run_id}",
    response_model=RunResponse,
)
async def get_run(
    run_id: str,
    service: ControlServiceDependency,
) -> RunResponse:
    try:
        record = await service.get_run(
            run_id
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RunResponse.from_record(
        record
    )


@router.post(
    "/{run_id}/stop",
    response_model=StopRunResponse,
)
async def stop_run(
    run_id: str,
    service: ControlServiceDependency,
) -> StopRunResponse:
    try:
        result = await service.stop_run(
            run_id
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RunNotStoppableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return StopRunResponse.from_result(
        result
    )


@router.post(
    "/{run_id}/replay",
    response_model=ReplayRunResponse,
)
async def replay_run(
    run_id: str,
    service: ControlServiceDependency,
) -> ReplayRunResponse:
    try:
        result = await service.replay_run(
            run_id
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RunNotReplayableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return ReplayRunResponse.from_result(
        result
    )
