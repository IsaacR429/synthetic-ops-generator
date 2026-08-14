from pathlib import Path

import pytest

from synthetic_ops_generator.history.loader import (
    load_historical_behaviour_profile,
)


def test_load_historical_behaviour_profile_rejects_empty_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Historical behaviour profile ID is required",
    ):
        load_historical_behaviour_profile("", directory=tmp_path)


def test_load_historical_behaviour_profile_rejects_nonexistent_directory(
    tmp_path: Path,
) -> None:
    nonexistent = tmp_path / "nonexistent"
    with pytest.raises(
        FileNotFoundError,
        match="Historical behaviour profile directory does not exist",
    ):
        load_historical_behaviour_profile("profile_id", directory=nonexistent)


def test_load_historical_behaviour_profile_rejects_unknown_id(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ValueError,
        match="Unknown Historical behaviour profile: unknown_id",
    ):
        load_historical_behaviour_profile("unknown_id", directory=tmp_path)


def test_loads_critical_interactive_historical_profile(
) -> None:
    profile = load_historical_behaviour_profile(
        "critical_interactive_nominal",
        directory=Path(
            "config/historical_profiles"
        ),
    )

    assert (
        profile.profile_id
        == "critical_interactive_nominal"
    )

    assert {
        *profile.metric_responses,
    } == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert (
        profile.persistence.persistence
        == 0.80
    )


def test_loads_business_workflow_historical_profile(
) -> None:
    profile = load_historical_behaviour_profile(
        "business_workflow_nominal",
        directory=Path(
            "config/historical_profiles"
        ),
    )

    assert (
        profile.profile_id
        == "business_workflow_nominal"
    )

    assert {
        *profile.metric_responses,
    } == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert (
        profile.persistence.persistence
        == 0.85
    )
