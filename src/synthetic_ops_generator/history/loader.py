from pathlib import Path

from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.history.models import (
    HistoricalBehaviourProfile,
)


def load_historical_behaviour_profile(
    profile_id: str,
    directory: str | Path = (
        "config/historical_profiles"
    ),
) -> HistoricalBehaviourProfile:
    if not profile_id:
        raise ValueError(
            "Historical behaviour profile ID "
            "is required."
        )

    profile_directory = Path(
        directory
    )

    if not profile_directory.exists():
        raise FileNotFoundError(
            "Historical behaviour profile "
            "directory does not exist: "
            f"{profile_directory}"
        )

    matches: list[
        HistoricalBehaviourProfile
    ] = []

    for path in sorted(
        profile_directory.glob(
            "*.yaml"
        )
    ):
        profile = load_yaml_model(
            path,
            HistoricalBehaviourProfile,
        )

        if profile.profile_id == profile_id:
            matches.append(
                profile
            )

    if not matches:
        raise ValueError(
            "Unknown Historical behaviour "
            f"profile: {profile_id}"
        )

    if len(matches) > 1:
        raise ValueError(
            "Duplicate Historical behaviour "
            f"profile ID: {profile_id}"
        )

    return matches[0]
