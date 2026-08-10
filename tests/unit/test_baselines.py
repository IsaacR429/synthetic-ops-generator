import pytest
from pydantic import ValidationError

from synthetic_ops_generator.baselines.models import (
    MetricBaseline,
)


def test_valid_baseline() -> None:
    baseline = MetricBaseline(
        metric_definition_id="request_latency",
        center=180,
        noise_stddev=15,
        lower_bound=100,
        upper_bound=260,
    )

    assert baseline.center == 180


def test_invalid_baseline_bounds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        MetricBaseline(
            metric_definition_id="request_latency",
            center=300,
            lower_bound=100,
            upper_bound=250,
        )