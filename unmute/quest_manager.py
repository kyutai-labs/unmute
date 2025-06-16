"""A desperate attempt at having some kind of RAII in Python.
Maybe we can achieve something more minimalistic with a TaskGroup and some try/finally blocks,
to be explored for future refactoring.
"""

import asyncio
import logging
import types
from collections.abc import Awaitable
from functools import partial
from typing import Any, Callable, TypeVar

from unmute.exceptions import (
    MissingServiceAtCapacity,
    MissingServiceTimeout,
    WebSocketClosedError,
)

T = TypeVar("T")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class Quest[T]:
    """A Quest is some async unit of work that consist of:
        - an init step, returning T.
        - a run step, using T.
        - a close step, cleaning up T.
    It can be "removed", e.g. cancelled or closed.
    To be used as a context manager to have some garantees on when
    the close step is run. Should be used along a `QuestManager` for best results.
    """

    def __init__(
        self,
        name: str,
        init: Callable[[], Awaitable[T]],
        run: Callable[[T], Awaitable[None]],
        close: Callable[[T], Awaitable[None]] | None = None,
    ):
        self.name = name
        self.init = init
        self.run = run
        self.close = close
        self.task = None
        self._data: asyncio.Future[T] = asyncio.Future()

    @staticmethod
    def from_run_step(name: str, run: Callable[[], Awaitable[None]]) -> "Quest[None]":
        async def _init() -> None:
            return None

        async def _run(_x: None) -> None:
            await run()

        return Quest(name, _init, _run)

    async def get(self) -> T:
        return await self._data

    def get_nowait(self) -> T | None:
        if self._data.done():
            return self._data.result()

    async def _run(self):
        logger.debug("Quest %s init starting...", self.name)
        try:
            data = await self.init()
        except Exception as exc:
            self._data.set_exception(exc)
            raise
        else:
            self._data.set_result(data)
        logger.debug("Quest %s running...", self.name)
        await self.run(data)

    async def __aenter__(self) -> asyncio.Future[None]:
        self.task = asyncio.create_task(self._run())
        return asyncio.ensure_future(self.task)

    async def __aexit__(self, *exc: Any):
        await self.remove()

    async def remove(self):
        assert self.task is not None
        try:
            if self.close is not None:
                # We explicitely wait on the init being successful to avoid weird mixed-status.
                logger.debug("Quest %s closing...", self.name)
                try:
                    if self._data.done() and self._data.exception() is None:
                        await self.close(await self.get())
                except asyncio.CancelledError:
                    pass
                self.close = None
        finally:
            logger.debug("Quest %s canceling...", self.name)
            self.task.cancel()


class QuestManager:
    """A Quest Manager. Enter its context, and schedule some Quests, any Quest with a name in common
    with a previous Quest will cancel it. Do some `asyncio.gather(manager.wait(), ...)` if you want
    to get any Quest exception bubbled up to you."""

    def __init__(self):
        self.quests: dict[str, Quest] = {}
        self._in_context = False
        self._future: asyncio.Future | None = None

    async def wait(self):
        assert self._future is not None
        await self._future

    async def add(self, quest: Quest[T]) -> Quest[T]:
        assert self._future is not None
        name = quest.name
        try:
            old = self.quests[name]
        except KeyError:
            pass
        else:
            await old.__aexit__(None)
        self.quests[name] = quest
        future = await quest.__aenter__()
        future.add_done_callback(partial(self._one_is_done, name, self._future))
        return quest

    async def remove(self, name: str):
        try:
            quest = self.quests.pop(name)
        except KeyError:
            return
        await quest.remove()

    @staticmethod
    def _one_is_done(name: str, agg_future: asyncio.Future, future: asyncio.Future):
        logger.debug("Quest %s is done.", name)
        try:
            future.result()
        except asyncio.CancelledError:
            logger.debug("Quest %s was cancelled.", name)
        except Exception as exc:
            logger.debug("Quest %s failed with %r.", name, exc)
            if not agg_future.done():
                agg_future.set_exception(exc)
        else:
            pass

    async def __aenter__(self) -> "QuestManager":
        assert self._future is None
        logger.debug("Quest manager entering...")
        self._future = asyncio.Future()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: types.TracebackType | None,
    ) -> None:
        assert self._future is not None
        logger.debug("Quest manager exiting...")
        for name, value in self.quests.items():
            try:
                await value.remove()
            except (
                MissingServiceAtCapacity,
                MissingServiceTimeout,
                WebSocketClosedError,
            ):
                pass
            except Exception:
                logger.exception(f"Error shutting down quest {name}.")
        logger.debug("All quests canceled...")
        self.quests.clear()
        if not self._future.done():
            self._future.set_result(None)
