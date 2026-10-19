from __future__ import annotations

from datetime import datetime, timezone

import pytest

from synthetic_ops_generator.domain.operational_test import (
    OperationalTest,
    TestCategory as OperationalTestCategory,
    TestExecutionStatus as OperationalTestExecutionStatus,
    TestResult as OperationalTestResult,
)
from synthetic_ops_generator.temporal.eligibility import (
    TemporalEligibilityStatus,
    TemporalWindow,
    assess_operational_test_temporal_eligibility,
)


def _dt(
    hour: int,
    minute: int = 0,
) -> datetime:
    return datetime(
        2026,
        6,
        10,
        hour,
        minute,
        tzinfo=timezone.utc,
    )


def _window() -> TemporalWindow:
    return TemporalWindow(
        window_id="post-change-validation",
        start_at=_dt(10, 30),
        end_at=_dt(11, 0),
    )


def _executed_test(
    *,
    executed_at: datetime,
    result: OperationalTestResult = OperationalTestResult.PASSED,
) -> OperationalTest:
    return OperationalTest(
        test_id="TEST-001",
        check_definition_id=(
            "application.post_deployment_smoke"
        ),
        chg_id="CHG-001",
        category=OperationalTestCategory.APPLICATION,
        test_type="smoke",
        name="Post-deployment smoke test",
        service="claims-processing",
        component="claims-api",
        mandatory=True,
        status=OperationalTestExecutionStatus.EXECUTED,
        result=result,
        planned_at=_dt(10, 20),
        executed_at=executed_at,
    )


def _planned_test() -> OperationalTest:
    return OperationalTest(
        test_id="TEST-001",
        check_definition_id=(
            "application.post_deployment_smoke"
        ),
        chg_id="CHG-001",
        category=OperationalTestCategory.APPLICATION,
        test_type="smoke",
        name="Post-deployment smoke test",
        service="claims-processing",
        component="claims-api",
        mandatory=True,
        status=OperationalTestExecutionStatus.PLANNED,
        result=None,
        planned_at=_dt(10, 20),
        executed_at=None,
    )


def test_executed_test_inside_window_is_eligible() -> None:
    test = _executed_test(
        executed_at=_dt(10, 45),
    )

    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=test,
            window=_window(),
        )
    )

    assert result.observed_at == test.executed_at

    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )

    assert result.is_eligible is True


def test_executed_test_before_window_is_ineligible() -> None:
    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=_executed_test(
                executed_at=_dt(10, 25),
            ),
            window=_window(),
        )
    )

    assert (
        result.status
        == TemporalEligibilityStatus.BEFORE_WINDOW
    )

    assert result.is_eligible is False


def test_executed_test_after_window_is_ineligible() -> None:
    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=_executed_test(
                executed_at=_dt(11, 15),
            ),
            window=_window(),
        )
    )

    assert (
        result.status
        == TemporalEligibilityStatus.AFTER_WINDOW
    )

    assert result.is_eligible is False


def test_planned_unexecuted_test_is_unavailable() -> None:
    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=_planned_test(),
            window=_window(),
        )
    )

    assert (
        result.status
        == TemporalEligibilityStatus.UNAVAILABLE
    )

    assert result.observed_at is None
    assert result.is_eligible is False


@pytest.mark.parametrize(
    "test_result",
    [
        OperationalTestResult.PASSED,
        OperationalTestResult.FAILED,
    ],
)
def test_test_result_does_not_change_temporal_eligibility(
    test_result: OperationalTestResult,
) -> None:
    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=_executed_test(
                executed_at=_dt(10, 45),
                result=test_result,
            ),
            window=_window(),
        )
    )

    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )

    assert result.is_eligible is True


def test_passed_test_outside_window_remains_temporally_ineligible() -> None:
    test = _executed_test(
        executed_at=_dt(11, 15),
        result=OperationalTestResult.PASSED,
    )

    assert test.result == OperationalTestResult.PASSED

    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=test,
            window=_window(),
        )
    )

    assert (
        result.status
        == TemporalEligibilityStatus.AFTER_WINDOW
    )

    assert result.is_eligible is False

    # Temporal interpretation must not mutate factual truth.
    assert test.result == OperationalTestResult.PASSED


def test_failed_test_inside_window_remains_temporally_eligible() -> None:
    test = _executed_test(
        executed_at=_dt(10, 45),
        result=OperationalTestResult.FAILED,
    )

    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=test,
            window=_window(),
        )
    )

    assert result.is_eligible is True
    assert test.result == OperationalTestResult.FAILED


def test_planned_at_does_not_substitute_for_execution_time() -> None:
    test = _planned_test()

    assert (
        _dt(10, 30)
        <= test.planned_at
        <= _dt(11, 0)
    ) is False

    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=test,
            window=_window(),
        )
    )

    assert (
        result.status
        == TemporalEligibilityStatus.UNAVAILABLE
    )


def test_forged_naive_execution_timestamp_is_rejected() -> None:
    test = _executed_test(
        executed_at=_dt(10, 45),
    ).model_copy(
        update={
            "executed_at": datetime(
                2026,
                6,
                10,
                10,
                45,
            )
        }
    )

    with pytest.raises(ValueError):
        assess_operational_test_temporal_eligibility(
            operational_test=test,
            window=_window(),
        )


def test_adapter_does_not_claim_requirement_or_governance_truth() -> None:
    result = (
        assess_operational_test_temporal_eligibility(
            operational_test=_executed_test(
                executed_at=_dt(10, 45),
            ),
            window=_window(),
        )
    )

    fields = result.model_fields

    assert "test_result" not in fields
    assert "requirement_status" not in fields
    assert "satisfied" not in fields
    assert "compliant" not in fields
    assert "blocking" not in fields
    assert "decision" not in fields
