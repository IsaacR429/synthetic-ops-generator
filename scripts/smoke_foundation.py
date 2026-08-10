import asyncio
from datetime import UTC, datetime

from synthetic_ops_generator.core.identifiers import IdFactory
from synthetic_ops_generator.domain.enums import Environment, RiskLevel
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.publishers.memory import InMemoryPublisher
from synthetic_ops_generator.scenarios.context import ScenarioContext


async def main() -> None:
    ids = IdFactory()
    publisher = InMemoryPublisher()

    context = ScenarioContext(
        scenario_id="BANK-01",
        run_id=ids.run_id(),
        chg_id=ids.change_id(),
        business_stream="payments",
        service="payment_service",
        component="payment_api",
        environment=Environment.PRODUCTION,
        risk=RiskLevel.MEDIUM,
        simulation_time=datetime.now(UTC),
        random_seed=4298,
    )

    event = GeneratedEvent(
        event_id=ids.event_id(),
        event_type="scenario.foundation_test",
        event_time=context.simulation_time,
        source_system="synthetic_generator",
        scenario_id=context.scenario_id,
        run_id=context.run_id,
        chg_id=context.chg_id,
        business_stream=context.business_stream,
        service=context.service,
        component=context.component,
        environment=context.environment,
        sequence_number=context.next_sequence(),
        data={
            "message": "Foundation is operational."
        },
    )

    await publisher.publish(event)

    for generated_event in publisher.events:
        print(
            generated_event.model_dump_json(
                indent=2
            )
        )


if __name__ == "__main__":
    asyncio.run(main())