from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from synthetic_ops_generator.domain.operational_test import (
    OperationalTest,
)
from synthetic_ops_generator.domain.operational_test import (
    TestCategory as Category,
)
from synthetic_ops_generator.domain.operational_test import (
    TestExecutionStatus as ExecutionStatus,
)
from synthetic_ops_generator.domain.operational_test import (
    TestResult as Result,
)


def test_valid_planned_infrastructure_test() -> None:
    planned_at = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    test = OperationalTest(
        test_id="TST0000001",
        chg_id="CHG0000001",
        category=Category.INFRASTRUCTURE,
        test_type="connectivity",
        name="Payment API connectivity",
        service="payment_service",
        component="payment_api",
        mandatory=True,
        status=ExecutionStatus.PLANNED,
        planned_at=planned_at,
    )

    assert test.status == ExecutionStatus.PLANNED
    assert test.result is None
    assert test.executed_at is None


def test_valid_executed_application_test() -> None:
    planned_at = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    test = OperationalTest(
        test_id="TST0000001",
        chg_id="CHG0000001",
        category=Category.APPLICATION,
        test_type="functional",
        name="Payment submission validation",
        service="payment_service",
        component="payment_api",
        mandatory=True,
        status=ExecutionStatus.EXECUTED,
        result=Result.PASSED,
        planned_at=planned_at,
        executed_at=(
            planned_at + timedelta(minutes=5)
        ),
    )

    assert test.status == ExecutionStatus.EXECUTED
    assert test.result == Result.PASSED


def test_planned_test_rejects_result() -> None:
    planned_at = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValidationError,
        match="Planned Test cannot have a result",
    ):
        OperationalTest(
            test_id="TST0000001",
            chg_id="CHG0000001",
            category=Category.APPLICATION,
            test_type="functional",
            name="Payment submission validation",
            service="payment_service",
            mandatory=True,
            status=ExecutionStatus.PLANNED,
            result=Result.PASSED,
            planned_at=planned_at,
        )


def test_executed_test_requires_execution_time() -> None:
    planned_at = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValidationError,
        match="requires an execution time",
    ):
        OperationalTest(
            test_id="TST0000001",
            chg_id="CHG0000001",
            category=Category.INFRASTRUCTURE,
            test_type="connectivity",
            name="Payment API connectivity",
            service="payment_service",
            mandatory=True,
            status=ExecutionStatus.EXECUTED,
            result=Result.PASSED,
            planned_at=planned_at,
        )


def test_executed_test_requires_result() -> None:
    planned_at = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValidationError,
        match="requires a result",
    ):
        OperationalTest(
            test_id="TST0000001",
            chg_id="CHG0000001",
            category=Category.INFRASTRUCTURE,
            test_type="connectivity",
            name="Payment API connectivity",
            service="payment_service",
            mandatory=True,
            status=ExecutionStatus.EXECUTED,
            planned_at=planned_at,
            executed_at=(
                planned_at + timedelta(minutes=5)
            ),
        )


def test_test_rejects_execution_before_planning() -> None:
    planned_at = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    )

    with pytest.raises(
        ValidationError,
        match="cannot occur before planning",
    ):
        OperationalTest(
            test_id="TST0000001",
            chg_id="CHG0000001",
            category=Category.APPLICATION,
            test_type="functional",
            name="Payment submission validation",
            service="payment_service",
            mandatory=True,
            status=ExecutionStatus.EXECUTED,
            result=Result.PASSED,
            planned_at=planned_at,
            executed_at=(
                planned_at - timedelta(seconds=1)
            ),
        )


def test_test_rejects_naive_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        8,
        11,
        10,
        0,
        tzinfo=UTC,
    ).replace(tzinfo=None)

    with pytest.raises(
        ValidationError,
        match="must be timezone-aware",
    ):
        OperationalTest(
            test_id="TST0000001",
            chg_id="CHG0000001",
            category=Category.INFRASTRUCTURE,
            test_type="connectivity",
            name="Payment API connectivity",
            service="payment_service",
            mandatory=True,
            status=ExecutionStatus.PLANNED,
            planned_at=naive_timestamp,
        )