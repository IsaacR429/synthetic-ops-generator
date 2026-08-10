from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.validator import (
    validate_scenario_against_enterprise,
)


def main() -> None:
    enterprise = load_enterprise(
        "config/enterprises/bank_alpha"
    )

    scenario = load_scenario(
        "config/scenarios/banking/BANK-01.yaml"
    )

    validate_scenario_against_enterprise(
        scenario,
        enterprise,
    )

    print(
        f"Loaded Scenario: "
        f"{scenario.name} ({scenario.scenario_id})"
    )

    print(
        f"  Enterprise: "
        f"{scenario.target.enterprise_id}"
    )

    print(
        f"  Business Stream: "
        f"{scenario.target.business_stream_id}"
    )

    print(
        f"  Service: "
        f"{scenario.target.service_id}"
    )

    print(
        f"  Components: "
        f"{len(scenario.target.component_ids)}"
    )

    state_path = " -> ".join(
        state.value
        for state in scenario.state_sequence
    )

    print(
        f"  State Plan: {state_path}"
    )

    print(
        f"  Behaviour Plans: "
        f"{len(scenario.behaviours)}"
    )

    print(
        "  Expected Result: "
        f"{scenario.expected_result.expected_decision.value}"
        " / "
        f"{scenario.expected_result.expected_action.value}"
        " / "
        f"{scenario.expected_result.expected_outcome.value}"
    )

    print(
        "  Enterprise Validation: PASSED"
    )


if __name__ == "__main__":
    main()