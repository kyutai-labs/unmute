import asyncio
import base64
import json
import logging
import os
import sys
from urllib.parse import urlparse
from urllib.request import urlopen

import numpy as np
import websockets

# Defaults target the "ROS on laptop + remote Unmute over SSH tunnel" setup.
# Example tunnel:
#   ssh -N -L 3333:localhost:80 <remote-host>
LAPTOP_WS_URL = os.environ.get("LAPTOP_WS_URL", "ws://127.0.0.1:8090")
UNMUTE_WS_URL = os.environ.get(
    "UNMUTE_WS_URL", "ws://127.0.0.1:3333/api/v1/realtime"
)
PCM_FORMAT = os.environ.get("PCM_FORMAT", "int16")
INPUT_SAMPLE_RATE = int(os.environ.get("INPUT_SAMPLE_RATE", "24000"))
UNMUTE_SAMPLE_RATE = int(os.environ.get("UNMUTE_SAMPLE_RATE", "24000"))
RESAMPLE_AUDIO = os.environ.get("RESAMPLE_AUDIO", "false").lower() == "true"
UNMUTE_VOICE = os.environ.get("UNMUTE_VOICE", None)
ALLOW_RECORDING = os.environ.get("ALLOW_RECORDING", "false").lower() == "true"
RECONNECT_DELAY_SEC = float(os.environ.get("RECONNECT_DELAY_SEC", "3.0"))
PRINT_TEXT_DELTAS = os.environ.get("PRINT_TEXT_DELTAS", "false").lower() == "true"
DEBUG_MIC_INPUT = os.environ.get("DEBUG_MIC_INPUT", "false").lower() == "true"
DEBUG_MIC_EVERY_N_PACKETS = int(os.environ.get("DEBUG_MIC_EVERY_N_PACKETS", "25"))
DEBUG_STT_EVENTS = os.environ.get("DEBUG_STT_EVENTS", "false").lower() == "true"
PRINT_USER_TRANSCRIPT_DELTAS = (
    os.environ.get("PRINT_USER_TRANSCRIPT_DELTAS", "true").lower() == "true"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("UnmuteBridge")


def _supports_color_output() -> bool:
    if os.environ.get("FORCE_COLOR") is not None:
        return True
    return sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _make_label(tag: str, color_code: str) -> str:
    if not _supports_color_output():
        return f"[{tag}]"
    reset = "\033[0m"
    return f"{color_code}[{tag}]{reset}"


USER_LABEL = _make_label("User", "\033[92m")
UNMUTE_LABEL = _make_label("Unmute", "\033[96m")


def _to_float32_pcm(raw_audio_b64: str, pcm_format: str) -> np.ndarray:
    decoded = base64.b64decode(raw_audio_b64)
    if pcm_format == "float32":
        return np.frombuffer(decoded, dtype=np.float32)
    if pcm_format == "int16":
        pcm_int16 = np.frombuffer(decoded, dtype=np.int16)
        return (pcm_int16.astype(np.float32) / 32768.0).clip(-1.0, 1.0)
    raise ValueError(f"Unsupported PCM_FORMAT={pcm_format!r}")


def _resample_linear(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    if audio.size == 0 or src_rate == dst_rate:
        return audio

    # Linear interpolation is fast, robust, and adequate for voice transport.
    src_len = audio.shape[0]
    dst_len = max(1, int(round(src_len * dst_rate / src_rate)))
    src_x = np.linspace(0.0, 1.0, num=src_len, endpoint=False)
    dst_x = np.linspace(0.0, 1.0, num=dst_len, endpoint=False)
    return np.interp(dst_x, src_x, audio).astype(np.float32)


def _encode_float32_b64(audio: np.ndarray) -> str:
    return base64.b64encode(audio.astype(np.float32).tobytes()).decode("utf-8")


def _audio_level_stats(audio: np.ndarray) -> tuple[float, float]:
    if audio.size == 0:
        return 0.0, 0.0
    rms = float(np.sqrt(np.mean(np.square(audio))))
    peak = float(np.max(np.abs(audio)))
    return rms, peak


def _needs_boundary_space(last_char: str | None, new_text: str) -> bool:
    if not last_char or not new_text:
        return False

    first_char = new_text[0]
    if last_char.isspace() or first_char.isspace():
        return False

    # Keep punctuation/contractions tight.
    if first_char in ",.!?;:)]}\"'":
        return False
    if last_char in "([{\"":
        return False
    if last_char in "'-/":
        return False

    # Word-like boundary without whitespace: add one.
    if last_char.isalnum() and first_char.isalnum():
        return True

    # Fallback: separate most non-space boundaries for readability.
    return True


async def _send_initial_session_update(unmute_ws: websockets.ClientConnection) -> None:
    """Initialize Unmute session so generation can start when audio arrives."""

    def _voices_url_from_ws_url(ws_url: str) -> str | None:
        parsed = urlparse(ws_url)
        if parsed.scheme not in {"ws", "wss"}:
            return None

        scheme = "https" if parsed.scheme == "wss" else "http"

        # Support both /v1/realtime and /api/v1/realtime style paths.
        path = parsed.path.rstrip("/")
        if path.endswith("/v1/realtime"):
            prefix = path[: -len("/v1/realtime")]
            voices_path = f"{prefix}/v1/voices"
        else:
            voices_path = "/v1/voices"

        return f"{scheme}://{parsed.netloc}{voices_path}"

    def _resolve_voice_and_instructions(
        requested_voice: str | None,
    ) -> tuple[str | None, dict | None]:
        if not requested_voice:
            return None, None

        voices_url = _voices_url_from_ws_url(UNMUTE_WS_URL)
        if not voices_url:
            logger.warning(
                "Couldn't infer voices URL from UNMUTE_WS_URL=%s; using UNMUTE_VOICE as-is",
                UNMUTE_WS_URL,
            )
            return requested_voice, None

        try:
            with urlopen(voices_url, timeout=5.0) as response:
                voices = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            logger.warning(
                "Failed to fetch voices from %s (%s); using UNMUTE_VOICE as-is",
                voices_url,
                exc,
            )
            return requested_voice, None

        for voice in voices:
            source = voice.get("source") or {}
            path_on_server = source.get("path_on_server")
            if requested_voice in {voice.get("name"), path_on_server}:
                return path_on_server or requested_voice, voice.get("instructions")

        logger.warning(
            "UNMUTE_VOICE=%s not found in /v1/voices; using value as raw voice id",
            requested_voice,
        )
        return requested_voice, None

    resolved_voice, resolved_instructions = await asyncio.to_thread(
        _resolve_voice_and_instructions,
        UNMUTE_VOICE,
    )

    session = {
        "allow_recording": ALLOW_RECORDING,
    }
    if resolved_voice:
        session["voice"] = resolved_voice
    if resolved_instructions:
        session["instructions"] = resolved_instructions

    payload = {
        "type": "session.update",
        "session": session,
    }
    await unmute_ws.send(json.dumps(payload))


async def run_bridge() -> None:
    if PCM_FORMAT not in {"int16", "float32"}:
        raise ValueError("PCM_FORMAT must be one of: int16, float32")

    while True:
        try:
            logger.info("Connecting to laptop audio websocket: %s", LAPTOP_WS_URL)
            async with websockets.connect(LAPTOP_WS_URL) as laptop_ws:
                logger.info("Laptop socket connected")

                logger.info("Connecting to Unmute websocket: %s", UNMUTE_WS_URL)
                async with websockets.connect(
                    UNMUTE_WS_URL,
                    subprotocols=[websockets.Subprotocol("realtime")],
                ) as unmute_ws:
                    logger.info("Unmute socket connected")
                    await _send_initial_session_update(unmute_ws)
                    logger.info(
                        (
                            "Bridge active (pcm_format=%s, allow_recording=%s, "
                            "resample=%s, input_sr=%s, unmute_sr=%s)"
                        ),
                        PCM_FORMAT,
                        ALLOW_RECORDING,
                        RESAMPLE_AUDIO,
                        INPUT_SAMPLE_RATE,
                        UNMUTE_SAMPLE_RATE,
                    )

                    async def forward_audio_to_unmute() -> None:
                        packet_count = 0
                        async for message in laptop_ws:
                            try:
                                data = json.loads(message)
                                if data.get("type") != "audio":
                                    continue

                                packet_count += 1

                                outgoing_audio_b64 = data["data"]
                                outgoing_format = PCM_FORMAT

                                mic_audio_f32 = _to_float32_pcm(data["data"], PCM_FORMAT)

                                if (
                                    DEBUG_MIC_INPUT
                                    and packet_count % max(1, DEBUG_MIC_EVERY_N_PACKETS) == 0
                                ):
                                    rms, peak = _audio_level_stats(mic_audio_f32)
                                    logger.info(
                                        (
                                            "Mic input packet=%s samples=%s rms=%.4f peak=%.4f "
                                            "in_format=%s"
                                        ),
                                        packet_count,
                                        mic_audio_f32.size,
                                        rms,
                                        peak,
                                        PCM_FORMAT,
                                    )

                                if RESAMPLE_AUDIO and INPUT_SAMPLE_RATE != UNMUTE_SAMPLE_RATE:
                                    resampled = _resample_linear(
                                        mic_audio_f32,
                                        src_rate=INPUT_SAMPLE_RATE,
                                        dst_rate=UNMUTE_SAMPLE_RATE,
                                    )
                                    outgoing_audio_b64 = _encode_float32_b64(resampled)
                                    outgoing_format = "float32"

                                unmute_msg = {
                                    "type": "unmute.input_audio_buffer.append_pcm",
                                    "audio": outgoing_audio_b64,
                                    "format": outgoing_format,
                                }
                                await unmute_ws.send(json.dumps(unmute_msg))
                            except Exception as exc:
                                logger.error("Error forwarding audio to Unmute: %s", exc)

                    async def forward_response_to_laptop() -> None:
                        text_deltas: list[str] = []
                        active_stream_speaker: str | None = None
                        last_char_by_speaker: dict[str, str | None] = {
                            "user": None,
                            "unmute": None,
                        }

                        def _print_stream_chunk(speaker: str, label: str, text: str) -> None:
                            nonlocal active_stream_speaker
                            if not text:
                                return
                            if active_stream_speaker != speaker:
                                if active_stream_speaker is not None:
                                    print("", flush=True)
                                print(f"{label} ", end="", flush=True)
                                active_stream_speaker = speaker
                            if _needs_boundary_space(last_char_by_speaker[speaker], text):
                                print(" ", end="", flush=True)
                            print(text, end="", flush=True)
                            last_char_by_speaker[speaker] = text[-1]

                        async for message in unmute_ws:
                            try:
                                data = json.loads(message)
                                msg_type = data.get("type")

                                if msg_type == "response.audio.delta":
                                    payload = {
                                        "type": "robot.voice_audio",
                                        "audio": data["delta"],
                                    }
                                    await laptop_ws.send(json.dumps(payload))
                                elif msg_type == "input_audio_buffer.speech_started":
                                    if DEBUG_STT_EVENTS:
                                        logger.debug("STT/VAD: speech_started")
                                elif msg_type == "input_audio_buffer.speech_stopped":
                                    if DEBUG_STT_EVENTS:
                                        logger.debug("STT/VAD: speech_stopped")
                                elif msg_type == "conversation.item.input_audio_transcription.delta":
                                    delta = data.get("delta", "")
                                    if PRINT_USER_TRANSCRIPT_DELTAS and delta:
                                        _print_stream_chunk("user", USER_LABEL, delta)
                                elif msg_type == "response.text.delta":
                                    text_delta = data.get("delta", "")
                                    if text_delta:
                                        text_deltas.append(text_delta)
                                        if PRINT_TEXT_DELTAS:
                                            _print_stream_chunk(
                                                "unmute", UNMUTE_LABEL, text_delta
                                            )
                                    payload = {
                                        "type": "robot.text",
                                        "text": text_delta,
                                    }
                                    await laptop_ws.send(json.dumps(payload))
                                elif msg_type == "response.text.done":
                                    # Streaming-only mode: no final full-sentence print.
                                    if active_stream_speaker == "unmute":
                                        print("", flush=True)
                                        active_stream_speaker = None
                                    last_char_by_speaker["unmute"] = None
                                    text_deltas.clear()
                                elif msg_type == "conversation.item.input_audio_transcription.completed":
                                    if PRINT_USER_TRANSCRIPT_DELTAS and active_stream_speaker == "user":
                                        print("", flush=True)
                                        active_stream_speaker = None
                                    last_char_by_speaker["user"] = None
                            except Exception as exc:
                                logger.error(
                                    "Error forwarding Unmute response: %s", exc
                                )

                    await asyncio.gather(
                        forward_audio_to_unmute(),
                        forward_response_to_laptop(),
                    )

        except Exception as exc:
            logger.error("Bridge connection error: %s", exc)
            logger.info("Retrying in %.1f seconds...", RECONNECT_DELAY_SEC)
            await asyncio.sleep(RECONNECT_DELAY_SEC)


if __name__ == "__main__":
    try:
        asyncio.run(run_bridge())
    except KeyboardInterrupt:
        logger.info("Bridge stopped by user")
