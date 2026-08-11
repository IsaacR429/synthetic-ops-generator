from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.change import (
    Approval,
    ApprovalStatus,
    Change,
    ChangeStatus,
)
from synthetic_ops_generator.domain.deployment import (
    Deployment,
    DeploymentOutcome,
    DeploymentStatus,
)
from synthetic_ops_generator.domain.enums import (
    Environment,
    RiskLevel,
)


def test_id_factory_generates_approval_id() -> None:
    ids = IdFactory()

    assert ids.approval_id() == "APR0000001"
    assert ids.approval_id() == "APR0000002"


def test_valid_change_with_approval() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    approval = Approval(
        approval_id="APR0000001",
        chg_id="CHG0000001",
        approval_type="implementation",
        status=ApprovalStatus.APPROVED,
        source="synthetic_itsm",
        timestamp=start,
    )

    change = Change(
        chg_id="CHG0000001",
        business_stream="payments",
        service="payment_service",
        components=[
            "payment_api",
            "payment_database",
        ],
        risk=RiskLevel.MEDIUM,
        owner="Payments Operations",
        environment=Environment.PRODUCTION,
        status=ChangeStatus.APPROVED,
        implementation_window_start=start,
        implementation_window_end=(
            start + timedelta(hours=1)
        ),
        approvals=[approval],
    )

    assert change.chg_id == "CHG0000001"
    assert change.approvals[0].status == ApprovalStatus.APPROVED


def test_change_rejects_invalid_implementation_window() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValidationError,
        match="Implementation window end",
    ):
        Change(
            chg_id="CHG0000001",
            business_stream="payments",
            service="payment_service",
            risk=RiskLevel.MEDIUM,
            owner="Payments Operations",
            environment=Environment.PRODUCTION,
            status=ChangeStatus.CREATED,
            implementation_window_start=start,
            implementation_window_end=start,
        )


def test_change_rejects_approval_for_different_change() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    approval = Approval(
        approval_id="APR0000001",
        chg_id="CHG9999999",
        approval_type="implementation",
        status=ApprovalStatus.APPROVED,
        source="synthetic_itsm",
        timestamp=start,
    )

    with pytest.raises(
        ValidationError,
        match="Approval CHG ID must match",
    ):
        Change(
            chg_id="CHG0000001",
            business_stream="payments",
            service="payment_service",
            risk=RiskLevel.MEDIUM,
            owner="Payments Operations",
            environment=Environment.PRODUCTION,
            status=ChangeStatus.APPROVED,
            implementation_window_start=start,
            implementation_window_end=(
                start + timedelta(hours=1)
            ),
            approvals=[approval],
        )


def test_valid_created_deployment() -> None:
    deployment = Deployment(
        deployment_id="DEP0000001",
        chg_id="CHG0000001",
        artifact="payment-api",
        artifact_version="2.5.0",
        service="payment_service",
        component="payment_api",
        status=DeploymentStatus.CREATED,
    )

    assert deployment.status == DeploymentStatus.CREATED
    assert deployment.outcome is None


def test_valid_completed_deployment() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    deployment = Deployment(
        deployment_id="DEP0000001",
        chg_id="CHG0000001",
        artifact="payment-api",
        artifact_version="2.5.0",
        service="payment_service",
        component="payment_api",
        start_time=start,
        completion_time=(
            start + timedelta(minutes=5)
        ),
        status=DeploymentStatus.COMPLETED,
        outcome=DeploymentOutcome.SUCCESSFUL,
    )

    assert deployment.outcome == DeploymentOutcome.SUCCESSFUL


def test_deployment_rejects_invalid_completion_time() -> None:
    start = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValidationError,
        match="Deployment completion must occur",
    ):
        Deployment(
            deployment_id="DEP0000001",
            chg_id="CHG0000001",
            artifact="payment-api",
            artifact_version="2.5.0",
            service="payment_service",
            start_time=start,
            completion_time=(
                start - timedelta(minutes=1)
            ),
            status=DeploymentStatus.COMPLETED,
            outcome=DeploymentOutcome.SUCCESSFUL,
        )
