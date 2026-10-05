from synthetic_ops_generator.capacity.evaluator import (
    classify_capacity,
)
from synthetic_ops_generator.capacity.models import (
    CapacityClassification,
    CapacityDirection,
    CapacityMetricEnvelope,
)


def test_higher_is_pressure_capacity_classification() -> None:
    envelope = CapacityMetricEnvelope(
        metric_definition_id="throughput",
        direction=CapacityDirection.HIGHER_IS_PRESSURE,
        pressure_threshold=900.0,
        saturation_threshold=1000.0,
    )

    assert (
        classify_capacity(
            envelope,
            observed_value=899.0,
        )
        == CapacityClassification.NORMAL
    )
    assert (
        classify_capacity(
            envelope,
            observed_value=900.0,
        )
        == CapacityClassification.PRESSURE
    )
    assert (
        classify_capacity(
            envelope,
            observed_value=1000.0,
        )
        == CapacityClassification.SATURATED
    )


def test_lower_is_pressure_capacity_classification() -> None:
    envelope = CapacityMetricEnvelope(
        metric_definition_id="remaining_capacity",
        direction=CapacityDirection.LOWER_IS_PRESSURE,
        pressure_threshold=20.0,
        saturation_threshold=10.0,
    )

    assert (
        classify_capacity(
            envelope,
            observed_value=21.0,
        )
        == CapacityClassification.NORMAL
    )
    assert (
        classify_capacity(
            envelope,
            observed_value=20.0,
        )
        == CapacityClassification.PRESSURE
    )
    assert (
        classify_capacity(
            envelope,
            observed_value=10.0,
        )
        == CapacityClassification.SATURATED
    )
