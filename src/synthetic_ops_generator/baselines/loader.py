from pathlib import Path

from synthetic_ops_generator.baselines.models import BaselineProfile
from synthetic_ops_generator.config.loader import load_yaml_model


def load_baseline_profile(
    profile_id: str,
    directory: str | Path = "config/baselines",
) -> BaselineProfile:
    if not profile_id:
        raise ValueError(
            "Baseline profile ID is required."
        )

    baseline_directory = Path(directory)

    if not baseline_directory.exists():
        raise FileNotFoundError(
            f"Baseline directory does not exist: "
            f"{baseline_directory}"
        )

    matches: list[BaselineProfile] = []

    for path in sorted(
        baseline_directory.glob("*.yaml")
    ):
        profile = load_yaml_model(
            path,
            BaselineProfile,
        )

        if profile.profile_id == profile_id:
            matches.append(profile)

    if not matches:
        raise ValueError(
            "Unknown Baseline profile: "
            f"{profile_id}"
        )

    if len(matches) > 1:
        raise ValueError(
            "Duplicate Baseline profile ID: "
            f"{profile_id}"
        )

    return matches[0]