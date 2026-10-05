from pathlib import Path

import pytest

from synthetic_ops_generator.capacity.loader import (
    load_capacity_profile,
)

CAPACITY_DIRECTORY = Path("config/capacity")


def test_loads_existing_capacity_by_profile_id() -> None:
    profile = load_capacity_profile(
        "critical_payment_capacity",
        CAPACITY_DIRECTORY,
    )

    assert (
        profile.profile_id
        == "critical_payment_capacity"
    )

    assert {
        *profile.metrics,
    } == {
        "throughput",
    }


def test_rejects_unknown_capacity_profile() -> None:
    with pytest.raises(
        ValueError,
        match="Unknown Capacity profile",
    ):
        load_capacity_profile(
            "does_not_exist",
            CAPACITY_DIRECTORY,
        )


def test_rejects_empty_capacity_profile_id() -> None:
    with pytest.raises(
        ValueError,
        match="Capacity profile ID is required",
    ):
        load_capacity_profile(
            "",
            CAPACITY_DIRECTORY,
        )
