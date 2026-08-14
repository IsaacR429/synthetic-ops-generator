import pytest

from synthetic_ops_generator.history.models import (
    HistoricalBehaviourProfile,
    HistoricalMetricResponse,
    TemporalActivityConfig,
    TemporalPersistenceConfig,
)


def test_temporal_activity_config_validates_hours_and_days() -> None:
    config = TemporalActivityConfig(
        business_start_hour=8,
        business_end_hour=18,
        business_days=[0, 1, 2, 3, 4],
        business_hours_factor=1.0,
        off_hours_factor=0.65,
        weekend_factor=0.45,
    )

    assert config.business_start_hour == 8
    assert config.business_end_hour == 18
    assert config.business_days == [0, 1, 2, 3, 4]


def test_temporal_activity_config_rejects_invalid_hours() -> None:
    with pytest.raises(
        ValueError, match="business_start_hour must be before"
    ):
        TemporalActivityConfig(
            business_start_hour=18,
            business_end_hour=8,
            business_days=[0, 1, 2, 3, 4],
            business_hours_factor=1.0,
            off_hours_factor=0.65,
            weekend_factor=0.45,
        )


def test_temporal_activity_config_rejects_invalid_days() -> None:
    with pytest.raises(
        ValueError, match="weekday values from 0 to 6"
    ):
        TemporalActivityConfig(
            business_start_hour=8,
            business_end_hour=18,
            business_days=[0, 1, 7],
            business_hours_factor=1.0,
            off_hours_factor=0.65,
            weekend_factor=0.45,
        )


def test_temporal_persistence_config_validates_bounds() -> None:
    config = TemporalPersistenceConfig(
        persistence=0.8,
        innovation_stddev=0.03,
        lower_bound=0.2,
        upper_bound=1.5,
    )
    assert config.persistence == 0.8


def test_temporal_persistence_config_rejects_invalid_bounds() -> None:
    with pytest.raises(
        ValueError, match="upper_bound cannot be below lower_bound"
    ):
        TemporalPersistenceConfig(
            persistence=0.8,
            innovation_stddev=0.03,
            lower_bound=1.5,
            upper_bound=0.2,
        )


def test_historical_behaviour_profile_rejects_mismatched_metric_keys() -> None:
    with pytest.raises(
        ValueError, match="key does not match metric_definition_id"
    ):
        HistoricalBehaviourProfile(
            profile_id="test_profile",
            name="Test Profile",
            temporal=TemporalActivityConfig(
                business_start_hour=8,
                business_end_hour=18,
                business_days=[0, 1, 2, 3, 4],
                business_hours_factor=1.0,
                off_hours_factor=0.65,
                weekend_factor=0.45,
            ),
            persistence=TemporalPersistenceConfig(
                persistence=0.8,
                innovation_stddev=0.03,
            ),
            metric_responses={
                "request_latency": HistoricalMetricResponse(
                    metric_definition_id="error_rate",
                    slope_per_activity_unit=0.1,
                )
            },
        )
