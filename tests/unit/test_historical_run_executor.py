import asyncio
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path

import pytest

from synthetic_ops_generator.config.enterprise_loader import (
    load_enterprise_configuration,
)
from synthetic_ops_generator.core.clock import (
    ManualSimulationClock,
)
from synthetic_ops_generator.core.identifiers import (
    IdFactory,
)
from synthetic_ops_generator.domain.enums import (
    OperationalState,
)
from synthetic_ops_generator.events.envelope import GeneratedEvent
from synthetic_ops_generator.history.executor import (
    HistoricalRunExecutor,
)
from synthetic_ops_generator.history.perturbation import (
    PerturbationCurveSpec,
)
from synthetic_ops_generator.publishers.base import (
    EventPublisher,
)
from synthetic_ops_generator.publishers.memory import (
    InMemoryPublisher,
)
from synthetic_ops_generator.scenarios.loader import (
    load_scenario,
)
from synthetic_ops_generator.scenarios.runner import (
    ScenarioRunner,
)

CONFIG_ROOT = Path("config")


class FailingPublisher(EventPublisher):
    def __init__(self, fail_at_count: int) -> None:
        self._fail_at_count = fail_at_count
        self.published: list[GeneratedEvent] = []

    async def publish(self, event: GeneratedEvent) -> None:
        if len(self.published) + 1 == self._fail_at_count:
            raise RuntimeError("Publisher failed intentionally")
        self.published.append(event)


class CancellingPublisher(EventPublisher):
    def __init__(self, cancel_at_count: int) -> None:
        self._cancel_at_count = cancel_at_count
        self.published: list[GeneratedEvent] = []

    async def publish(self, event: GeneratedEvent) -> None:
        self.published.append(event)
        if len(self.published) == self._cancel_at_count:
            raise asyncio.CancelledError()


@pytest.mark.asyncio
async def test_historical_executor_runs_complete_bank_02() -> None:
    scenario = load_scenario("config/scenarios/banking/BANK-02.yaml")
    enterprise = load_enterprise_configuration("config/enterprises/bank_alpha")

    ids = IdFactory()
    anchor_time = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(anchor_time)
    runner = ScenarioRunner(ids=ids, clock=clock)

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    publisher = InMemoryPublisher()
    executor = HistoricalRunExecutor()

    progress_reports: list[tuple[OperationalState, int]] = []

    def on_progress(state: OperationalState, count: int) -> None:
        progress_reports.append((state, count))

    result = await executor.execute(
        scenario=scenario,
        enterprise=enterprise,
        context=context,
        ids=ids,
        publisher=publisher,
        anchor_time=anchor_time,
        curve_spec=PerturbationCurveSpec(
            degradation_samples=4,
            plateau_samples=2,
            recovery_samples=4,
        ),
        config_root=CONFIG_ROOT,
        progress_observer=on_progress,
    )

    assert result.event_count == 48
    assert result.final_state == OperationalState.COMPLETED
    assert len(publisher.events) == 48

    assert clock.now() == anchor_time

    reported_states = {state for state, _ in progress_reports}
    assert OperationalState.NORMAL in reported_states
    assert OperationalState.OBSERVING in reported_states
    assert OperationalState.DEGRADED in reported_states
    assert OperationalState.RECOVERY in reported_states
    assert OperationalState.COMPLETED in reported_states

    counts = [count for _, count in progress_reports]
    assert all(c1 <= c2 for c1, c2 in pairwise(counts))
    assert all(c1 < c2 for c1, c2 in pairwise(counts[:-1]))
    assert counts[-1] == 48
    assert progress_reports[-1] == (OperationalState.COMPLETED, 48)


@pytest.mark.asyncio
async def test_historical_executor_cancellation_propagates() -> None:
    scenario = load_scenario("config/scenarios/banking/BANK-02.yaml")
    enterprise = load_enterprise_configuration("config/enterprises/bank_alpha")

    ids = IdFactory()
    anchor_time = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(anchor_time)
    runner = ScenarioRunner(ids=ids, clock=clock)

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    publisher = CancellingPublisher(cancel_at_count=10)
    executor = HistoricalRunExecutor()

    with pytest.raises(asyncio.CancelledError):
        await executor.execute(
            scenario=scenario,
            enterprise=enterprise,
            context=context,
            ids=ids,
            publisher=publisher,
            anchor_time=anchor_time,
            curve_spec=PerturbationCurveSpec(
                degradation_samples=4,
                plateau_samples=2,
                recovery_samples=4,
            ),
            config_root=CONFIG_ROOT,
        )

    assert len(publisher.published) == 10


@pytest.mark.asyncio
async def test_historical_executor_partial_publication_on_failure() -> None:
    scenario = load_scenario("config/scenarios/banking/BANK-02.yaml")
    enterprise = load_enterprise_configuration("config/enterprises/bank_alpha")

    ids = IdFactory()
    anchor_time = datetime(2026, 8, 14, 10, 0, tzinfo=UTC)
    clock = ManualSimulationClock(anchor_time)
    runner = ScenarioRunner(ids=ids, clock=clock)

    context = runner.create_context(
        scenario=scenario,
        enterprise=enterprise,
        random_seed=42,
    )

    publisher = FailingPublisher(fail_at_count=7)
    executor = HistoricalRunExecutor()

    with pytest.raises(RuntimeError, match="Publisher failed intentionally"):
        await executor.execute(
            scenario=scenario,
            enterprise=enterprise,
            context=context,
            ids=ids,
            publisher=publisher,
            anchor_time=anchor_time,
            curve_spec=PerturbationCurveSpec(
                degradation_samples=4,
                plateau_samples=2,
                recovery_samples=4,
            ),
            config_root=CONFIG_ROOT,
        )

    assert len(publisher.published) == 6
