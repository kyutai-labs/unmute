import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

import msgpack
from pydantic import BaseModel, Field

import unmute.openai_realtime_api_events as ora

RECORDINGS_DIR = Path(__file__).parents[1] / "recordings"


logger = logging.getLogger(__name__)

EventSender = Literal["client", "server"]


class RecorderEvent(BaseModel):
    timestamp_wall: float
    event_sender: EventSender
    data: Annotated[ora.Event, Field(discriminator="type")]


class Recorder:
    def __init__(self):
        self.path = RECORDINGS_DIR / (make_filename() + ".msgpack")
        self._events = []
        self.queue = asyncio.Queue()
        # The lock lets us know if the recorder is running.
        self.loop_lock = asyncio.Lock()
        self.max_events = 750

    async def run(self):
        await self._loop()

    async def add_event(self, event_sender: EventSender, data: ora.Event):
        """If the recorder is not actually running, the event will be ignored."""
        if not self.loop_lock.locked():
            return

        if len(self._events) >= self.max_events:
            return

        await self.queue.put(
            RecorderEvent(
                timestamp_wall=datetime.now().timestamp(),
                event_sender=event_sender,
                data=data,
            )
        )

    async def _loop(self):
        async with self.loop_lock:
            while True:
                event = await self.queue.get()
                self._events.append(event)
                if len(self._events) >= self.max_events:
                    await self._save()

    async def _save(self):
        RECORDINGS_DIR.mkdir(exist_ok=True)

        # Streaming?
        with self.path.open("wb") as f:
            f.write(msgpack.dumps([event.dict() for event in self._events]))

        logger.info(f"Saved recording with {len(self._events)} messages to {self.path}")


def make_filename() -> str:
    """Create a filename based on the current timestamp, without a suffix."""
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
