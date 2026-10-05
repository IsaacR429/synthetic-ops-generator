from synthetic_ops_generator.capacity.models import (
    CapacityClassification,
    CapacityDirection,
    CapacityMetricEnvelope,
)


def classify_capacity(
    envelope: CapacityMetricEnvelope,
    *,
    observed_value: float,
) -> CapacityClassification:
    if (
        envelope.direction
        == CapacityDirection.HIGHER_IS_PRESSURE
    ):
        if observed_value >= envelope.saturation_threshold:
            return CapacityClassification.SATURATED
        if observed_value >= envelope.pressure_threshold:
            return CapacityClassification.PRESSURE
        return CapacityClassification.NORMAL

    if (
        envelope.direction
        == CapacityDirection.LOWER_IS_PRESSURE
    ):
        if observed_value <= envelope.saturation_threshold:
            return CapacityClassification.SATURATED
        if observed_value <= envelope.pressure_threshold:
            return CapacityClassification.PRESSURE
        return CapacityClassification.NORMAL

    raise ValueError(
        "Unsupported capacity direction: "
        f"{envelope.direction}"
    )
