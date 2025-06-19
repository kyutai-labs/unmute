import asyncio
import logging
import subprocess
import time
from hashlib import md5
from pathlib import Path
from typing import Literal, Sequence

import librosa
import numpy as np
import sphn
import tqdm.auto
import websockets
from pydantic import BaseModel, Field
from ruamel.yaml import YAML

from unmute.kyutai_constants import HEADERS
from unmute.llm.system_prompt import Instructions
from unmute.tts.freesound_download import (
    OUTPUT_DIR,
    FreesoundVoiceSource,
    download_sound,
)

TTS_OUTPUT_CACHE_DIR = OUTPUT_DIR / "tts-outputs"
CFG_PARAM = "cfg_alpha=1.5"

SERVER_VOICES_DIR_DEV = Path("/home") / Path.home().stem / "models" / "tts-voices"
DEV_SERVER = "pod2"

SERVER_VOICES_DIR_PROD = Path("/scratch/models/")
PROD_SERVER = "root@unmute.sh"

logger = logging.getLogger(__name__)


async def text_to_speech_non_streaming(
    url: str, tts_text: str, voice: str
) -> np.ndarray:
    text_hash = md5(tts_text.encode("utf-8")).hexdigest()[:4]
    filename = f"{voice.replace('/', '__')}_{tts_text[:20]}_{text_hash}_{CFG_PARAM}.ogg"
    cache_file = TTS_OUTPUT_CACHE_DIR / filename

    if cache_file.exists():
        logger.info(f"Using cached file: {cache_file}")
        audio, sr = sphn.read_opus(cache_file)
        assert audio.ndim == 2
        audio = audio[0]  # to mono

        # resample to 24kHz
        audio = librosa.resample(audio, orig_sr=sr, target_sr=24000)

        return audio

    output: np.ndarray | None = None

    async def send_messages(websocket: websockets.ClientConnection):
        global start_time
        start_time = None
        for word in tts_text.split(" "):
            await websocket.send(word)
            if start_time is None:
                start_time = time.time()
            await asyncio.sleep(0.1)
        await websocket.send(b"\0")

    async def receive_messages(websocket: websockets.ClientConnection):
        global start_time
        nonlocal output
        first_token = True
        reader = sphn.OpusStreamReader(24000)
        all_data = []
        total_len = 0
        pbar = tqdm.auto.tqdm("TTS inference")
        while True:
            try:
                response = await websocket.recv()
            except websockets.exceptions.ConnectionClosedOK:
                return np.concatenate(all_data, axis=0)
            if start_time is not None and first_token:
                first_token = False
            total_len += len(response)
            pbar.update(len(response))
            if isinstance(response, bytes):
                audio_data = reader.append_bytes(response)
                all_data.append(audio_data)

    async def websocket_client():
        uri = f"{url}/api/tts_streaming?voice={voice}&{CFG_PARAM}"

        async with websockets.connect(uri, additional_headers=HEADERS) as websocket:
            send_task = asyncio.create_task(send_messages(websocket))
            receive_task = asyncio.create_task(receive_messages(websocket))
            _, audio = await asyncio.gather(send_task, receive_task)
            return audio

    audio = await websocket_client()

    # Cache for later
    TTS_OUTPUT_CACHE_DIR.mkdir(exist_ok=True, parents=True)
    sphn.write_opus(cache_file, audio[np.newaxis, :], sample_rate=24000)
    logger.info(f"Cached file: {cache_file}")

    return audio


def subprocess_with_retries(command: Sequence[str | Path], attempts: int = 3):
    """
    Run a subprocess command with retries on failure.
    """
    for attempt in range(attempts):
        try:
            subprocess.run(command, check=True)
            return  # Exit the function if successful
        except subprocess.CalledProcessError as e:
            if attempt == attempts - 1:
                raise  # If it's the last attempt, re-raise the exception
            else:
                logger.warning(f"Attempt {attempt + 1} to run {command} failed: {e}")


def upload_voice_to_dev(local_path: Path, path_on_server: str | Path):
    logger.info(f"Uploading {local_path} to {path_on_server}")

    subprocess_with_retries(
        [
            "rsync",
            local_path,
            DEV_SERVER + ":" + str(SERVER_VOICES_DIR_DEV / path_on_server),
        ],
    )


def copy_voice_to_prod(path_on_server: str):
    logger.info(f"Copying {path_on_server}(.safetensors) from dev to prod")

    paths = [path_on_server, path_on_server + ".safetensors"]

    for path in paths:
        command = [
            "scp",
            DEV_SERVER + ":" + str(SERVER_VOICES_DIR_DEV / path),
            PROD_SERVER + ":" + str(SERVER_VOICES_DIR_PROD / path),
        ]
        print("Running command:", " ".join(command))
        subprocess_with_retries(command, attempts=1)


def find_enhanced_version(original_path: Path) -> Path | None:
    # Manually created via https://podcast.adobe.com/en/enhance
    clean_path = OUTPUT_DIR / "voices-clean" / (original_path.stem + "-enhanced-v2.wav")

    if clean_path.exists():
        return clean_path
    else:
        return None


class FileVoiceSource(BaseModel):
    source_type: Literal["file"] = "file"
    path_on_server: str
    description: str | None = None
    description_link: str | None = None


class VoiceSample(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = None
    comment: str | None = None
    good: bool | None = None
    instructions: Instructions | None = None
    source: FreesoundVoiceSource | FileVoiceSource = Field(discriminator="source_type")


class VoiceList:
    def __init__(self):
        self.path = Path(__file__).parents[2] / "voices.yaml"
        with self.path.open() as f:
            self.voices = [VoiceSample(**sound) for sound in YAML().load(f)]

    async def upload_to_server(self):
        async def process_voice(voice: VoiceSample):
            if not voice.good:
                logger.debug(
                    f"skipping {voice.name or voice.source.path_on_server}, "
                    "not marked as good"
                )
                return

            if isinstance(voice.source, FreesoundVoiceSource):
                logger.info(f"downloading {voice.name}")
                (downloaded_path, voice_source_with_metadata) = await asyncio.to_thread(
                    download_sound,
                    voice.source,
                )
                voice.source = voice_source_with_metadata
            else:
                downloaded_path = OUTPUT_DIR / "voices" / voice.source.path_on_server
                if not downloaded_path.exists():
                    raise FileNotFoundError(
                        f"File {downloaded_path} does not exist locally"
                    )

            clean_path = find_enhanced_version(downloaded_path)
            if clean_path:
                logger.info(f"Using enhanced version: {clean_path}")
                downloaded_path = clean_path

            assert voice.source.path_on_server is not None

            await asyncio.to_thread(
                upload_voice_to_dev,
                downloaded_path,
                path_on_server=voice.source.path_on_server,
            )

        await asyncio.gather(*(process_voice(voice) for voice in self.voices))

    def save(self):
        with self.path.open("w") as f:
            yaml = YAML()
            yaml.width = float("inf")  # Disable line wrapping

            # Put "good" voices first, then undecided, then bad.
            # The sort is stable, so the order is otherwise preserved
            voices = sorted(
                self.voices, key=lambda x: {True: 0, None: 1, False: 2}[x.good]
            )
            yaml.dump(
                [
                    voice.model_dump(
                        # This would also exclude the discriminator field :(
                        # exclude_defaults=True,
                        exclude_none=True,
                        exclude={"source": {"sound_instance": ["previews"]}},  # type: ignore
                    )
                    for voice in voices
                ],
                f,
            )
