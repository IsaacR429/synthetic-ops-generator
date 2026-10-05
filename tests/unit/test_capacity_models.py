import pytest
from pydantic import ValidationError

from synthetic_ops_generator.capacity.models import (
    CapacityClassification,
    CapacityDirection,
    CapacityMetricEnvelope,
    CapacityProfile,
)


def test_capacity_metric_supports_higher_pressure_thresholds() -> None:
    envelope = CapacityMetricEnvelope(
        metric_definition_id="throughput",
        direction=CapacityDirection.HIGHER_IS_PRESSURE,
        pressure_threshold=900.0,
        saturation_threshold=1000.0,
    )
    assert envelope.metric_definition_id == "throughput"
    assert (
        envelope.direction
        == CapacityDirection.HIGHER_IS_PRESSURE
    )
    assert envelope.pressure_threshold == 900.0
    assert envelope.saturation_threshold == 1000.0


def test_higher_pressure_capacity_requires_saturation_above_pressure() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Saturation threshold must be greater than "
            "pressure threshold for higher-is-pressure capacity"
        ),
    ):
        CapacityMetricEnvelope(
            metric_definition_id="throughput",
            direction=CapacityDirection.HIGHER_IS_PRESSURE,
            pressure_threshold=1000.0,
            saturation_threshold=900.0,
        )


def test_lower_pressure_capacity_accepts_saturation_below_pressure() -> None:
    envelope = CapacityMetricEnvelope(
        metric_definition_id="remaining_connections",
        direction=CapacityDirection.LOWER_IS_PRESSURE,
        pressure_threshold=20.0,
        saturation_threshold=10.0,
    )
    assert envelope.pressure_threshold == 20.0
    assert envelope.saturation_threshold == 10.0


def test_lower_pressure_capacity_requires_saturation_below_pressure() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Saturation threshold must be less than "
            "pressure threshold for lower-is-pressure capacity"
        ),
    ):
        CapacityMetricEnvelope(
            metric_definition_id="remaining_connections",
            direction=CapacityDirection.LOWER_IS_PRESSURE,
            pressure_threshold=10.0,
            saturation_threshold=20.0,
        )


def test_capacity_profile_contains_metric_envelopes() -> None:
    profile = CapacityProfile(
        profile_id="critical_payment_capacity",
        name="Critical Payment Capacity",
        description=(
            "Synthetic capacity envelope for the "
            "mission-critical payment service."
        ),
        metrics={
            "throughput": CapacityMetricEnvelope(
                metric_definition_id="throughput",
                direction=(
                    CapacityDirection.HIGHER_IS_PRESSURE
                ),
                pressure_threshold=900.0,
                saturation_threshold=1000.0,
            ),
        },
    )
    assert (
        profile.profile_id
        == "critical_payment_capacity"
    )
    assert set(profile.metrics) == {
        "throughput",
    }
    assert (
        profile.metrics["throughput"]
        .saturation_threshold
        == 1000.0
    )


def test_capacity_profile_requires_at_least_one_metric() -> None:
    with pytest.raises(ValidationError):
        CapacityProfile(
            profile_id="empty_capacity",
            name="Empty Capacity",
            metrics={},
        )


def test_capacity_profile_metric_key_must_match_definition_id() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "Capacity metric key does not match "
            "metric_definition_id"
        ),
    ):
        CapacityProfile(
            profile_id="invalid_capacity",
            name="Invalid Capacity",
            metrics={
                "throughput": CapacityMetricEnvelope(
                    metric_definition_id="error_rate",
                    direction=(
                        CapacityDirection.HIGHER_IS_PRESSURE
                    ),
                    pressure_threshold=900.0,
                    saturation_threshold=1000.0,
                ),
            },
        )


def test_capacity_classification_values_are_stable() -> None:
    assert CapacityClassification.NORMAL.value == "normal"
    assert CapacityClassification.PRESSURE.value == "pressure"
    assert CapacityClassification.SATURATED.value == "saturated"
