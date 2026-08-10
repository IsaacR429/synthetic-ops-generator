from pathlib import Path

from synthetic_ops_generator.config.loader import (
    load_yaml_model,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioDefinition,
)


def load_scenario(
    path: str | Path,
) -> ScenarioDefinition:
    return load_yaml_model(
        path,
        ScenarioDefinition,
    )