from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    status,
)

from synthetic_ops_generator.api.models import (
    ReplayRunResponse,
    RunEventsResponse,
    RunResponse,
    StartRunRequest,
    StartRunResponse,
    StopRunResponse,
)
from synthetic_ops_generator.control.models import (
    RunStatus,
)
from synthetic_ops_generator.control.service import (
    ControlService,
    RunExecutionModeNotSupportedError,
    RunNotFoundError,
    RunNotReplayableError,
    RunNotStoppableError,
    ScenarioNotFoundError,
)
from synthetic_ops_generator.domain.enums import (
    SourceDomain,
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
            historical_configuration=(
                request.historical_configuration()
            ),
            generation_lifecycle=(
                request.generation_lifecycle
            ),
            continuous_configuration=(
                request.continuous_configuration()
            ),
        )
    except ScenarioNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except RunExecutionModeNotSupportedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return StartRunResponse.from_result(
        result
    )


@router.get(
    "",
    response_model=list[RunResponse],
)
async def list_runs(
    service: ControlServiceDependency,
    status: RunStatus | None = None,
) -> list[RunResponse]:
    records = await service.list_runs(
        status=status
    )

    return [
        RunResponse.from_record(record)
        for record in records
    ]


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


@router.get(
    "/{run_id}/events",
    response_model=RunEventsResponse,
)
async def get_run_events(
    run_id: str,
    service: ControlServiceDependency,
    source_domain: SourceDomain | None = None,
    source_system: str | None = None,
    event_type: str | None = None,
    service_name: Annotated[
        str | None,
        Query(alias="service"),
    ] = None,
    component: str | None = None,
    after_sequence_number: Annotated[
        int | None,
        Query(ge=0),
    ] = None,
    limit: Annotated[
        int | None,
        Query(gt=0),
    ] = None,
) -> RunEventsResponse:
    has_filters = any(
        value is not None
        for value in (
            source_domain,
            source_system,
            event_type,
            service_name,
            component,
        )
    )

    has_pagination = (
        after_sequence_number is not None
        or limit is not None
    )

    try:
        if not has_filters and not has_pagination:
            events = await service.get_run_events(
                run_id
            )

            return RunEventsResponse.from_events(
                run_id=run_id,
                events=events,
            )

        retained_event_count = (
            await service.count_run_events(
                run_id,
                source_domain=source_domain,
                source_system=source_system,
                event_type=event_type,
                service=service_name,
                component=component,
            )
        )

        fetch_limit = (
            limit + 1
            if limit is not None
            else None
        )

        events = await service.query_run_events(
            run_id,
            source_domain=source_domain,
            source_system=source_system,
            event_type=event_type,
            service=service_name,
            component=component,
            after_sequence_number=(
                after_sequence_number
            ),
            limit=fetch_limit,
        )
    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    if limit is None:
        page_events = events
        next_after_sequence_number = None
    else:
        has_more = len(events) > limit

        page_events = (
            events[:limit]
            if has_more
            else events
        )

        next_after_sequence_number = (
            page_events[-1].sequence_number
            if has_more and page_events
            else None
        )

    return RunEventsResponse.from_events(
        run_id=run_id,
        events=page_events,
        retained_event_count=retained_event_count,
        next_after_sequence_number=(
            next_after_sequence_number
        ),
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
