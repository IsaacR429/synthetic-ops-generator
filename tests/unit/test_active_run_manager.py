import asyncio

import pytest

from synthetic_ops_generator.control.active_run_manager import (
    ActiveRunManager,
)


@pytest.mark.asyncio
async def test_active_run_manager_tracks_active_run() -> None:
    manager = ActiveRunManager()

    started = asyncio.Event()
    release = asyncio.Event()

    async def execution() -> None:
        started.set()
        await release.wait()

    manager.start(
        "RUN0000001",
        execution,
    )

    await started.wait()

    assert manager.is_active(
        "RUN0000001"
    )

    assert manager.active_run_ids() == (
        "RUN0000001",
    )

    release.set()

    for _ in range(10):
        if not manager.is_active(
            "RUN0000001"
        ):
            break

        await asyncio.sleep(0)

    assert not manager.is_active(
        "RUN0000001"
    )

    assert manager.active_run_ids() == ()


@pytest.mark.asyncio
async def test_active_run_manager_stops_active_run() -> None:
    manager = ActiveRunManager()

    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def execution() -> None:
        started.set()

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    manager.start(
        "RUN0000001",
        execution,
    )

    await started.wait()

    stopped = await manager.stop(
        "RUN0000001"
    )

    await cancelled.wait()

    assert stopped is True

    assert not manager.is_active(
        "RUN0000001"
    )

    assert (
        await manager.stop(
            "RUN0000001"
        )
        is False
    )


@pytest.mark.asyncio
async def test_active_run_manager_rejects_duplicate_active_run() -> None:
    manager = ActiveRunManager()

    started = asyncio.Event()

    async def execution() -> None:
        started.set()
        await asyncio.Event().wait()

    manager.start(
        "RUN0000001",
        execution,
    )

    await started.wait()

    with pytest.raises(
        ValueError,
        match=(
            "Run is already active: "
            "RUN0000001"
        ),
    ):
        manager.start(
            "RUN0000001",
            execution,
        )

    await manager.shutdown()


@pytest.mark.asyncio
async def test_active_run_manager_shutdown_cancels_all_runs() -> None:
    manager = ActiveRunManager()

    started_one = asyncio.Event()
    started_two = asyncio.Event()

    cancelled_one = asyncio.Event()
    cancelled_two = asyncio.Event()

    async def first_execution() -> None:
        started_one.set()

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled_one.set()
            raise

    async def second_execution() -> None:
        started_two.set()

        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled_two.set()
            raise

    manager.start(
        "RUN0000001",
        first_execution,
    )

    manager.start(
        "RUN0000002",
        second_execution,
    )

    await started_one.wait()
    await started_two.wait()

    assert manager.active_run_ids() == (
        "RUN0000001",
        "RUN0000002",
    )

    await manager.shutdown()

    await cancelled_one.wait()
    await cancelled_two.wait()

    assert manager.active_run_ids() == ()