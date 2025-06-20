import asyncio
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

import unmute.openai_realtime_api_events as ora

SAVE_EVERY_N_EVENTS = 100

logger = logging.getLogger(__name__)

EventSender = Literal["client", "server"]


class RecorderEvent(BaseModel):
    timestamp_wall: float
    event_sender: EventSender
    data: Annotated[ora.Event, Field(discriminator="type")]


class Recorder:
    """Record the events sent between the client and the server to a file.

    Doesn't include the user audio for privacy reasons.
    """

    def __init__(self, recordings_dir: Path):
        self.path = recordings_dir / (make_filename() + ".jsonl")
        recordings_dir.mkdir(exist_ok=True)
        self._unsaved_events = []
        self.queue = asyncio.Queue()
        # The lock lets us know if the recorder is running.
        self.loop_lock = asyncio.Lock()

    async def run(self):
        logger.info(f"Starting recording into {self.path}")
        await self._loop()

    async def add_event(self, event_sender: EventSender, data: ora.Event):
        """If the recorder is not actually running, the event will be ignored."""
        if not self.loop_lock.locked():
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
                self._unsaved_events.append(event)

                if len(self._unsaved_events) >= SAVE_EVERY_N_EVENTS:
                    with self.path.open("a") as f:
                        for e in self._unsaved_events:
                            f.write(e.model_dump_json() + "\n")

                        self._unsaved_events = []


def make_filename() -> str:
    """Create a unique filename based on the current timestamp and a short UUID, without a suffix."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    unique_id = uuid.uuid4().hex[:4]
    return f"{timestamp}_{unique_id}"
