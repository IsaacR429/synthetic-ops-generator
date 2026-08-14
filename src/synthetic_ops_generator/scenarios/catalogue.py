from pathlib import Path

from synthetic_ops_generator.scenarios.loader import load_scenario
from synthetic_ops_generator.scenarios.models import ScenarioDefinition


class ScenarioCatalogue:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def list_scenarios(self) -> tuple[ScenarioDefinition, ...]:
        if not self._root.exists():
            raise FileNotFoundError(
                f"Scenario catalogue root does not exist: {self._root}"
            )

        scenario_paths = sorted(
            self._root.rglob("*.yaml")
        )

        scenarios: dict[str, ScenarioDefinition] = {}

        for path in scenario_paths:
            scenario = load_scenario(path)

            if scenario.scenario_id in scenarios:
                raise ValueError(
                    "Duplicate Scenario ID detected: "
                    f"{scenario.scenario_id}"
                )

            scenarios[scenario.scenario_id] = scenario

        return tuple(
            sorted(
                scenarios.values(),
                key=lambda scenario: scenario.scenario_id,
            )
        )

    def get_scenario(
        self,
        scenario_id: str,
    ) -> ScenarioDefinition | None:
        for scenario in self.list_scenarios():
            if scenario.scenario_id == scenario_id:
                return scenario

        return None
