from synthetic_ops_generator.baselines.models import (
    BaselineProfile,
)
from synthetic_ops_generator.benchmarks.models import (
    BenchmarkCatalogue,
    BenchmarkReferenceCatalogue,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
)


def test_metric_catalogue_loads() -> None:
    catalogue = load_yaml_model(
        "config/metrics/definitions.yaml",
        MetricCatalogue,
    )

    assert "request_latency" in catalogue.definitions


def test_benchmark_catalogue_loads() -> None:
    catalogue = load_yaml_model(
        "config/benchmarks/synthetic_defaults.yaml",
        BenchmarkCatalogue,
    )

    assert (
        "critical_interactive_transaction"
        in catalogue.profiles
    )


def test_reference_catalogue_loads() -> None:
    catalogue = load_yaml_model(
        "config/benchmarks/external_references.yaml",
        BenchmarkReferenceCatalogue,
    )

    assert "google_sre_slo_methodology" in catalogue.references


def test_baseline_profile_loads() -> None:
    profile = load_yaml_model(
        "config/baselines/synthetic_defaults.yaml",
        BaselineProfile,
    )

    assert "request_latency" in profile.metrics