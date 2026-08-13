from pathlib import Path

import pytest

from synthetic_ops_generator.baselines.loader import (
    load_baseline_profile,
)

BASELINE_DIRECTORY = Path("config/baselines")


def test_loads_existing_baseline_by_profile_id() -> None:
    profile = load_baseline_profile(
        "critical_interactive_nominal",
        BASELINE_DIRECTORY,
    )

    assert (
        profile.profile_id
        == "critical_interactive_nominal"
    )


def test_loads_business_workflow_baseline() -> None:
    profile = load_baseline_profile(
        "business_workflow_nominal",
        BASELINE_DIRECTORY,
    )

    assert (
        profile.profile_id
        == "business_workflow_nominal"
    )

    assert {
        *profile.metrics,
    } == {
        "request_latency",
        "error_rate",
        "availability",
    }


def test_rejects_unknown_baseline_profile() -> None:
    with pytest.raises(
        ValueError,
        match="Unknown Baseline profile",
    ):
        load_baseline_profile(
            "does_not_exist",
            BASELINE_DIRECTORY,
        )


def test_rejects_empty_profile_id() -> None:
    with pytest.raises(
        ValueError,
        match="Baseline profile ID is required",
    ):
        load_baseline_profile(
            "",
            BASELINE_DIRECTORY,
        )
