import os
from pathlib import Path

from unmute.websocket_utils import http_to_ws

HEADERS = {"kyutai-api-key": "public_token"}

# The defaults are already ws://, but make the env vars support http:// and https://
STT_SERVER = http_to_ws(os.environ.get("KYUTAI_STT_URL", "ws://localhost:8090"))
TTS_SERVER = http_to_ws(os.environ.get("KYUTAI_TTS_URL", "ws://localhost:8089"))
LLM_SERVER = os.environ.get("KYUTAI_LLM_URL", "http://localhost:8091")
KYUTAI_LLM_MODEL = os.environ.get("KYUTAI_LLM_MODEL")
VOICE_CLONING_SERVER = os.environ.get(
    "KYUTAI_VOICE_CLONING_URL", "http://localhost:8092"
)
# If None, a dict-based cache will be used instead of Redis
REDIS_SERVER = os.environ.get("KYUTAI_REDIS_URL")

SPEECH_TO_TEXT_PATH = "/api/asr-streaming"
TEXT_TO_SPEECH_PATH = "/api/tts_streaming"

repo_root = Path(__file__).parents[1]
VOICE_DONATION_DIR = Path(
    os.environ.get("KYUTAI_VOICE_DONATION_DIR", repo_root / "voices" / "donation")
)

# If None, recordings will not be saved
_recordings_dir = os.environ.get("KYUTAI_RECORDINGS_DIR")
RECORDINGS_DIR = Path(_recordings_dir) if _recordings_dir else None

# Also checked on the frontend, see constant of the same name
MAX_VOICE_FILE_SIZE_MB = 4


SAMPLE_RATE = 24000
SAMPLES_PER_FRAME = 1920
FRAME_TIME_SEC = SAMPLES_PER_FRAME / SAMPLE_RATE  # 0.08
# TODO: make it so that we can read this from the ASR server?
STT_DELAY_SEC = 0.5
