import asyncio
from collections.abc import Awaitable, Callable

RunExecutionFactory = Callable[[], Awaitable[None]]


class ActiveRunManager:
    """
    Owns in-process asynchronous Scenario execution tasks.

    Persistent Run metadata remains the responsibility of RunStore.
    """

    def __init__(self) -> None:
        self._tasks: dict[
            str,
            asyncio.Task[None],
        ] = {}

    def start(
        self,
        run_id: str,
        execution_factory: RunExecutionFactory,
    ) -> None:
        if not run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        existing = self._tasks.get(
            run_id
        )

        if (
            existing is not None
            and not existing.done()
        ):
            raise ValueError(
                f"Run is already active: {run_id}"
            )

        task = asyncio.create_task(
            execution_factory(),
            name=f"scenario-run:{run_id}",
        )

        self._tasks[run_id] = task

        task.add_done_callback(
            lambda completed_task: (
                self._handle_done(
                    run_id,
                    completed_task,
                )
            )
        )

    def is_active(
        self,
        run_id: str,
    ) -> bool:
        task = self._tasks.get(
            run_id
        )

        return (
            task is not None
            and not task.done()
        )

    def active_run_ids(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                run_id
                for run_id, task
                in self._tasks.items()
                if not task.done()
            )
        )

    async def stop(
        self,
        run_id: str,
    ) -> bool:
        if not run_id.strip():
            raise ValueError(
                "Run ID is required."
            )

        task = self._tasks.get(
            run_id
        )

        if task is None or task.done():
            self._tasks.pop(
                run_id,
                None,
            )
            return False

        task.cancel()

        try:
            await task
        except asyncio.CancelledError:
            pass
        finally:
            if self._tasks.get(run_id) is task:
                self._tasks.pop(
                    run_id,
                    None,
                )

        return True

    async def shutdown(self) -> None:
        tasks = tuple(
            self._tasks.values()
        )

        for task in tasks:
            if not task.done():
                task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        self._tasks.clear()

    def _handle_done(
        self,
        run_id: str,
        task: asyncio.Task[None],
    ) -> None:
        if self._tasks.get(run_id) is task:
            self._tasks.pop(
                run_id,
                None,
            )

        if task.cancelled():
            return

        # Retrieve any exception so an independently running
        # task cannot produce "Task exception was never retrieved".
        task.exception()