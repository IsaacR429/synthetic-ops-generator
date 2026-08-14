from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.metrics.runtime import (
    resolve_metric_runtime_configuration,
)

CONFIG_ROOT = Path("config")


@pytest.mark.parametrize(
    (
        "enterprise_path",
        "service_id",
        "expected_baseline",
        "expected_benchmark",
    ),
    [
        (
            Path("config/enterprises/bank_alpha"),
            "payment_service",
            "critical_interactive_nominal",
            "critical_interactive_transaction",
        ),
        (
            Path("config/enterprises/insurer_alpha"),
            "claims_service",
            "business_workflow_nominal",
            "business_critical_interactive",
        ),
    ],
)
def test_resolves_metric_runtime_configuration(
    enterprise_path: Path,
    service_id: str,
    expected_baseline: str,
    expected_benchmark: str,
) -> None:
    enterprise = load_enterprise_configuration(
        enterprise_path
    )

    service = next(
        s for s in enterprise.services if s.service_id == service_id
    )

    runtime = (
        resolve_metric_runtime_configuration(
            service=service,
            config_root=CONFIG_ROOT,
        )
    )

    assert (
        runtime.baseline_profile.profile_id
        == expected_baseline
    )

    assert (
        runtime.benchmark_profile_id
        == expected_benchmark
    )

    assert set(
        runtime.resolved_benchmarks
    ) == {
        "request_latency",
        "error_rate",
        "availability",
    }

    assert set(
        runtime.resolved_benchmarks
    ).issubset(
        runtime.definitions
    )


def test_metric_runtime_requires_baseline_profile(
) -> None:
    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/bank_alpha"
        )
    )

    service = enterprise.services[0].model_copy(
        update={
            "baseline_profile_id": None
        }
    )

    with pytest.raises(
        ValueError,
        match="does not define a Baseline profile",
    ):
        resolve_metric_runtime_configuration(
            service=service,
            config_root=CONFIG_ROOT,
        )


def test_metric_runtime_requires_benchmark_profile(
) -> None:
    enterprise = (
        load_enterprise_configuration(
            "config/enterprises/bank_alpha"
        )
    )

    service = enterprise.services[0].model_copy(
        update={
            "benchmark_profile_id": None
        }
    )

    with pytest.raises(
        ValueError,
        match="does not define a Benchmark profile",
    ):
        resolve_metric_runtime_configuration(
            service=service,
            config_root=CONFIG_ROOT,
        )
