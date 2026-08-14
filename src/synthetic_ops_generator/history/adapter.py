from dataclasses import dataclass

from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)
from synthetic_ops_generator.history.correlation import (
    MetricActivityResponse,
)
from synthetic_ops_generator.history.models import (
    HistoricalBehaviourProfile,
)
from synthetic_ops_generator.history.temporal import (
    TemporalActivityProfile,
    TemporalPersistenceProfile,
)


@dataclass(frozen=True)
class HistoricalRuntimeProfile:
    profile_id: str
    activity_profile: TemporalActivityProfile
    persistence_profile: TemporalPersistenceProfile
    metric_responses: dict[str, MetricActivityResponse]


def build_historical_runtime_profile(
    *,
    baseline_profile: BaselineProfile,
    historical_profile: HistoricalBehaviourProfile,
) -> HistoricalRuntimeProfile:
    if (
        baseline_profile.profile_id
        != historical_profile.profile_id
    ):
        raise ValueError(
            "Baseline profile and Historical "
            "behaviour profile must have the "
            "same profile ID: "
            f"'{baseline_profile.profile_id}' vs "
            f"'{historical_profile.profile_id}'."
        )

    baseline_metric_ids = set(
        baseline_profile.metrics.keys()
    )
    response_metric_ids = set(
        historical_profile.metric_responses.keys()
    )

    missing_responses = (
        baseline_metric_ids
        - response_metric_ids
    )

    if missing_responses:
        formatted = ", ".join(
            sorted(missing_responses)
        )

        raise ValueError(
            "Historical behaviour profile is "
            "missing metric responses for: "
            f"{formatted}"
        )

    unknown_responses = (
        response_metric_ids
        - baseline_metric_ids
    )

    if unknown_responses:
        formatted = ", ".join(
            sorted(unknown_responses)
        )

        raise ValueError(
            "Historical behaviour profile "
            "contains metric responses that "
            "are not present in the Baseline "
            f"profile: {formatted}"
        )

    temporal = historical_profile.temporal

    persistence = historical_profile.persistence

    activity_profile = TemporalActivityProfile(
        business_start_hour=(
            temporal.business_start_hour
        ),
        business_end_hour=(
            temporal.business_end_hour
        ),
        business_days=frozenset(
            temporal.business_days
        ),
        business_hours_factor=(
            temporal.business_hours_factor
        ),
        off_hours_factor=(
            temporal.off_hours_factor
        ),
        weekend_factor=(
            temporal.weekend_factor
        ),
    )

    persistence_profile = (
        TemporalPersistenceProfile(
            persistence=(
                persistence.persistence
            ),
            innovation_stddev=(
                persistence.innovation_stddev
            ),
            lower_bound=(
                persistence.lower_bound
            ),
            upper_bound=(
                persistence.upper_bound
            ),
        )
    )

    metric_responses = {
        metric_id: MetricActivityResponse(
            metric_definition_id=(
                response.metric_definition_id
            ),
            slope_per_activity_unit=(
                response.slope_per_activity_unit
            ),
        )
        for metric_id, response
        in historical_profile.metric_responses.items()
    }

    return HistoricalRuntimeProfile(
        profile_id=baseline_profile.profile_id,
        activity_profile=activity_profile,
        persistence_profile=(
            persistence_profile
        ),
        metric_responses=metric_responses,
    )
