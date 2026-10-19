from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from synthetic_ops_generator.domain.evidence import Evidence
from synthetic_ops_generator.temporal.eligibility import (
    TemporalEligibilityStatus,
    TemporalWindow,
    assess_evidence_temporal_eligibility,
    assess_temporal_eligibility,
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


def _evidence(
    *,
    captured_at: datetime,
) -> Evidence:
    return Evidence(
        evidence_id="EVD-001",
        chg_id="CHG-001",
        evidence_type="post_change_observation",
        title="Post-change observation",
        service="claims-processing",
        component="claims-api",
        captured_at=captured_at,
        source_event_ids=["EVT-001"],
    )


def test_before_window_is_ineligible() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(10, 29),
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.BEFORE_WINDOW
    )
    assert result.is_eligible is False


def test_window_start_boundary_is_eligible() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(10, 30),
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )
    assert result.is_eligible is True


def test_inside_window_is_eligible() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(10, 45),
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )
    assert result.is_eligible is True


def test_window_end_boundary_is_eligible() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(11, 0),
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )
    assert result.is_eligible is True


def test_after_window_is_ineligible() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(11, 1),
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.AFTER_WINDOW
    )
    assert result.is_eligible is False


def test_missing_observation_time_is_unavailable() -> None:
    result = assess_temporal_eligibility(
        observed_at=None,
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.UNAVAILABLE
    )
    assert result.is_eligible is False
    assert result.observed_at is None


def test_evidence_adapter_uses_captured_at() -> None:
    evidence = _evidence(
        captured_at=_dt(10, 45),
    )

    result = assess_evidence_temporal_eligibility(
        evidence=evidence,
        window=_window(),
    )

    assert result.observed_at == evidence.captured_at
    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )
    assert result.is_eligible is True


def test_evidence_label_does_not_override_timestamp() -> None:
    evidence = _evidence(
        captured_at=_dt(11, 15),
    )

    assert (
        evidence.evidence_type
        == "post_change_observation"
    )

    result = assess_evidence_temporal_eligibility(
        evidence=evidence,
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.AFTER_WINDOW
    )
    assert result.is_eligible is False


def test_temporal_window_requires_timezone_aware_start() -> None:
    with pytest.raises(ValueError):
        TemporalWindow(
            window_id="window-1",
            start_at=datetime(
                2026,
                6,
                10,
                10,
                30,
            ),
            end_at=_dt(11, 0),
        )


def test_temporal_window_requires_timezone_aware_end() -> None:
    with pytest.raises(ValueError):
        TemporalWindow(
            window_id="window-1",
            start_at=_dt(10, 30),
            end_at=datetime(
                2026,
                6,
                10,
                11,
                0,
            ),
        )


@pytest.mark.parametrize(
    "end_at",
    [
        _dt(10, 30),
        _dt(10, 29),
    ],
)
def test_temporal_window_requires_positive_duration(
    end_at: datetime,
) -> None:
    with pytest.raises(ValueError):
        TemporalWindow(
            window_id="window-1",
            start_at=_dt(10, 30),
            end_at=end_at,
        )


def test_forged_invalid_window_is_rejected_by_resolver() -> None:
    window = _window().model_copy(
        update={
            "end_at": _dt(10, 0),
        }
    )

    with pytest.raises(ValueError):
        assess_temporal_eligibility(
            observed_at=_dt(10, 45),
            window=window,
        )


def test_naive_observation_time_is_rejected() -> None:
    with pytest.raises(ValueError):
        assess_temporal_eligibility(
            observed_at=datetime(
                2026,
                6,
                10,
                10,
                45,
            ),
            window=_window(),
        )


def test_equivalent_instant_with_different_offset_is_supported() -> None:
    offset = timezone(
        timedelta(hours=2)
    )

    result = assess_temporal_eligibility(
        observed_at=datetime(
            2026,
            6,
            10,
            12,
            45,
            tzinfo=offset,
        ),
        window=_window(),
    )

    assert (
        result.status
        == TemporalEligibilityStatus.WITHIN_WINDOW
    )
    assert result.is_eligible is True


def test_result_preserves_window_audit_facts() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(10, 45),
        window=_window(),
    )

    assert result.window_id == "post-change-validation"
    assert result.window_start_at == _dt(10, 30)
    assert result.window_end_at == _dt(11, 0)
    assert result.observed_at == _dt(10, 45)


def test_result_is_frozen() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(10, 45),
        window=_window(),
    )

    with pytest.raises(Exception):
        result.is_eligible = False


def test_result_does_not_claim_evidence_or_governance_truth() -> None:
    result = assess_temporal_eligibility(
        observed_at=_dt(10, 45),
        window=_window(),
    )

    fields = result.model_fields

    assert "result" not in fields
    assert "passed" not in fields
    assert "failed" not in fields
    assert "satisfied" not in fields
    assert "compliant" not in fields
    assert "blocking" not in fields
    assert "decision" not in fields
