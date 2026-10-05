from dataclasses import dataclass
from pathlib import Path

from synthetic_ops_generator.capacity.loader import (
    load_capacity_profile,
)
from synthetic_ops_generator.capacity.models import (
    CapacityProfile,
)
from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.domain.enterprise import (
    Service,
)
from synthetic_ops_generator.metrics.models import (
    MetricCatalogue,
    MetricDefinition,
)


@dataclass(frozen=True)
class CapacityRuntimeConfiguration:
    profile: CapacityProfile
    definitions: dict[str, MetricDefinition]


def resolve_capacity_runtime_configuration(
    *,
    service: Service,
    config_root: str | Path,
) -> CapacityRuntimeConfiguration | None:
    if service.capacity_profile_id is None:
        return None

    root = Path(config_root)

    profile = load_capacity_profile(
        service.capacity_profile_id,
        directory=root / "capacity",
    )

    metric_catalogue = load_yaml_model(
        root / "metrics" / "definitions.yaml",
        MetricCatalogue,
    )

    definitions: dict[
        str,
        MetricDefinition,
    ] = {}

    for metric_id in profile.metrics:
        definition = (
            metric_catalogue.definitions.get(
                metric_id
            )
        )

        if definition is None:
            raise ValueError(
                "Capacity profile references unknown "
                "Metric Definition: "
                f"{metric_id}"
            )

        definitions[metric_id] = definition

    return CapacityRuntimeConfiguration(
        profile=profile,
        definitions=definitions,
    )
