from dataclasses import dataclass

from synthetic_ops_generator.generators.base import (
    SourceGenerator,
)
from synthetic_ops_generator.scenarios.context import (
    ScenarioExecutionTarget,
)
from synthetic_ops_generator.scenarios.models import (
    ScenarioBehaviour,
)


@dataclass(frozen=True)
class SourceExecutionBinding:
    behaviour: ScenarioBehaviour
    generator: SourceGenerator
    execution_target: ScenarioExecutionTarget | None
