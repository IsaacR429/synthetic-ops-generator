from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)

from synthetic_ops_generator.api.models import (
    EnterpriseDetailResponse,
    EnterpriseSummaryResponse,
)
from synthetic_ops_generator.config.enterprise_catalogue import (
    EnterpriseCatalogue,
)

router = APIRouter(
    prefix="/enterprises",
    tags=["enterprises"],
)


def get_enterprise_catalogue(
    request: Request,
) -> EnterpriseCatalogue:
    return request.app.state.enterprise_catalogue


EnterpriseCatalogueDependency = Annotated[
    EnterpriseCatalogue,
    Depends(get_enterprise_catalogue),
]


@router.get(
    "",
    response_model=list[
        EnterpriseSummaryResponse
    ],
)
async def list_enterprises(
    catalogue: EnterpriseCatalogueDependency,
) -> list[EnterpriseSummaryResponse]:
    return [
        EnterpriseSummaryResponse.from_enterprise(
            enterprise
        )
        for enterprise
        in catalogue.list_enterprises()
    ]


@router.get(
    "/{enterprise_id}",
    response_model=EnterpriseDetailResponse,
)
async def get_enterprise(
    enterprise_id: str,
    catalogue: EnterpriseCatalogueDependency,
) -> EnterpriseDetailResponse:
    enterprise = catalogue.get_enterprise(
        enterprise_id
    )

    if enterprise is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Enterprise '{enterprise_id}' "
                "was not found."
            ),
        )

    return (
        EnterpriseDetailResponse.from_enterprise(
            enterprise
        )
    )
