import shutil
from pathlib import Path

import pytest

from synthetic_ops_generator.capacity.runtime import (
    resolve_capacity_runtime_configuration,
)
from synthetic_ops_generator.domain.enterprise import Service
from synthetic_ops_generator.domain.enums import Criticality

CONFIG_ROOT = Path("config")


def test_resolves_capacity_runtime_for_service() -> None:
    service = Service(
        service_id="payment_service",
        name="Payment Processing",
        business_stream_id="payments",
        owner="payments_operations",
        criticality=Criticality.CRITICAL,
        capacity_profile_id="critical_payment_capacity",
    )

    runtime = resolve_capacity_runtime_configuration(
        service=service,
        config_root=CONFIG_ROOT,
    )

    assert runtime is not None
    assert (
        runtime.profile.profile_id
        == "critical_payment_capacity"
    )
    assert set(runtime.definitions) == {
        "throughput",
    }
    assert (
        runtime.definitions["throughput"]
        .metric_definition_id
        == "throughput"
    )


def test_service_without_capacity_profile_has_no_capacity_runtime() -> None:
    service = Service(
        service_id="identity_service",
        name="Identity Service",
        business_stream_id="customer_identity",
        owner="identity_operations",
        criticality=Criticality.CRITICAL,
    )

    runtime = resolve_capacity_runtime_configuration(
        service=service,
        config_root=CONFIG_ROOT,
    )

    assert runtime is None


def test_rejects_capacity_profile_with_unknown_metric_definition(
    tmp_path: Path,
) -> None:
    metrics_directory = tmp_path / "metrics"
    metrics_directory.mkdir()
    shutil.copy(
        CONFIG_ROOT / "metrics" / "definitions.yaml",
        metrics_directory / "definitions.yaml",
    )
    capacity_directory = tmp_path / "capacity"
    capacity_directory.mkdir()
    (
        capacity_directory
        / "invalid_capacity.yaml"
    ).write_text(
        """profile_id: invalid_capacity
name: Invalid Capacity
metrics:
  unknown_capacity_metric:
    metric_definition_id: unknown_capacity_metric
    direction: higher_is_pressure
    pressure_threshold: 900
    saturation_threshold: 1000""".strip(),
        encoding="utf-8",
    )
    service = Service(
        service_id="payment_service",
        name="Payment Processing",
        business_stream_id="payments",
        owner="payments_operations",
        criticality=Criticality.CRITICAL,
        capacity_profile_id="invalid_capacity",
    )
    with pytest.raises(
        ValueError,
        match=(
            "Capacity profile references unknown "
            "Metric Definition: unknown_capacity_metric"
        ),
    ):
        resolve_capacity_runtime_configuration(
            service=service,
            config_root=tmp_path,
        )
