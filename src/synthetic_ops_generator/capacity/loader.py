from pathlib import Path

from synthetic_ops_generator.capacity.models import (
    CapacityProfile,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)


def load_capacity_profile(
    profile_id: str,
    directory: str | Path = "config/capacity",
) -> CapacityProfile:
    if not profile_id:
        raise ValueError(
            "Capacity profile ID is required."
        )

    capacity_directory = Path(directory)

    if not capacity_directory.exists():
        raise FileNotFoundError(
            "Capacity directory does not exist: "
            f"{capacity_directory}"
        )

    matches: list[CapacityProfile] = []

    for path in sorted(
        capacity_directory.glob("*.yaml")
    ):
        profile = load_yaml_model(
            path,
            CapacityProfile,
        )

        if profile.profile_id == profile_id:
            matches.append(profile)

    if not matches:
        raise ValueError(
            "Unknown Capacity profile: "
            f"{profile_id}"
        )

    if len(matches) > 1:
        raise ValueError(
            "Duplicate Capacity profile ID: "
            f"{profile_id}"
        )

    return matches[0]
