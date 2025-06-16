import argparse
import asyncio
import base64
import json
import logging
import multiprocessing
import random
import time
from pathlib import Path
from typing import Annotated

import librosa
import numpy as np
import pydub
import pydub.playback
import requests
import sphn
import websockets
from fastrtc import CloseStream, audio_to_float32, audio_to_int16
from pydantic import Field, TypeAdapter
from pydantic.json import pydantic_encoder

import unmute.openai_realtime_api_events as ora
from unmute.kyutai_constants import SAMPLE_RATE
from unmute.llm.system_prompt import SmalltalkInstructions
from unmute.loadtest.loadtest_result import (
    AssistantMessageTiming,
    BenchmarkAssistantMessage,
    BenchmarkMessage,
    BenchmarkUserMessage,
    UserMessageTiming,
    combine_latency_reports,
    make_latency_report,
)
from unmute.timer import PhasesStopwatch
from unmute.tts.realtime_queue import RealtimeQueue
from unmute.tts.voices import VoiceSample
from unmute.websocket_utils import ws_to_http

TARGET_CHANNELS = 1  # Mono
MAX_N_MESSAGES = 6

emit_logger = logging.getLogger("emit")
receive_logger = logging.getLogger("receive")
main_logger = logging.getLogger("main")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(process)d %(name)s %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def base64_encode_audio(audio: np.ndarray):
    pcm_bytes = audio_to_int16(audio)
    encoded = base64.b64encode(pcm_bytes).decode("ascii")
    return encoded


def preview_audio(audio: np.ndarray, playback_speed: float = 1.0):
    audio = audio_to_float32(audio)

    if playback_speed != 1.0:
        audio = librosa.effects.time_stretch(audio, rate=playback_speed)

    audio_segment = pydub.AudioSegment(
        data=audio_to_int16(audio),
        sample_width=2,
        frame_rate=SAMPLE_RATE,
        channels=TARGET_CHANNELS,
    )
    # audio.export("output.wav", format="wav")
    pydub.playback.play(audio_segment)


async def emit_loop(
    websocket: websockets.ClientConnection,
    audio_to_emit: asyncio.Queue[np.ndarray | CloseStream],
    voice: str,
):
    # An initial update is necessary for the model to send the conversation starter
    await websocket.send(
        ora.SessionUpdate(
            session=ora.SessionConfig(
                instructions=SmalltalkInstructions(),
                voice=voice,
            )
        ).model_dump_json()
    )

    OUTPUT_FRAME_SIZE = 1920

    queue = RealtimeQueue()
    queue.start_if_not_started()
    n_chunks_sent = 0
    writer = sphn.OpusStreamWriter(SAMPLE_RATE)

    def queue_up_chunk(audio: np.ndarray):
        nonlocal n_chunks_sent

        assert audio.ndim == 1
        assert audio.shape[0] <= OUTPUT_FRAME_SIZE

        opus_bytes = writer.append_pcm(audio)
        if opus_bytes:
            queue.put(opus_bytes, n_chunks_sent * OUTPUT_FRAME_SIZE / SAMPLE_RATE)

        n_chunks_sent += 1

    try:
        while True:
            try:
                data = audio_to_emit.get_nowait()

                if isinstance(data, CloseStream):
                    emit_logger.info("Received CloseStream, closing connection.")
                    break

                emit_logger.info(f"Queuing up {len(data) / SAMPLE_RATE:.1f}s of audio.")

                for i in range(0, len(data), OUTPUT_FRAME_SIZE):
                    queue_up_chunk(data[i : i + OUTPUT_FRAME_SIZE])
            except asyncio.QueueEmpty:
                pass

            if queue.empty():
                queue_up_chunk(np.zeros(OUTPUT_FRAME_SIZE, dtype=np.float32))

            async for _, opus_bytes in queue:
                await websocket.send(
                    ora.InputAudioBufferAppend(
                        audio=base64.b64encode(opus_bytes).decode("utf-8"),
                    ).model_dump_json()
                )

    except websockets.ConnectionClosed as e:
        emit_logger.info(f"Connection closed while sending messages: {e}")

    emit_logger.info("Finished sending messages.")


async def receive_loop(
    websocket: websockets.ClientConnection,
    audio_to_emit: asyncio.Queue[np.ndarray | CloseStream],
    audio_files_data: list[np.ndarray],
    listen: bool,
) -> list[BenchmarkMessage] | BaseException:
    # ^ We use BaseException in the return type above because later we want to also
    # be able to use KeyboardInterrupt as an error
    opus_reader = sphn.OpusStreamReader(SAMPLE_RATE)
    current_audio_chunks = []

    assistant_stopwatch = PhasesStopwatch(
        ["response_created", "text_start", "audio_start", "audio_end"]
    )
    user_stopwatch = PhasesStopwatch(["audio_start", "text_start", "audio_end"])

    chat_history = []
    benchmark_chat_history: list[BenchmarkMessage] = []

    try:
        async for message_raw in websocket:
            assert isinstance(message_raw, str), (
                f"Message is not a string: {message_raw}"
            )
            message: ora.ServerEvent = TypeAdapter(
                Annotated[ora.ServerEvent, Field(discriminator="type")]
            ).validate_json(message_raw)

            if isinstance(message, ora.ResponseCreated):  # start
                assistant_stopwatch.time_phase_if_not_started("response_created")

                if user_stopwatch.phase_dict_partial()["audio_start"] is not None:
                    # In case we are timing a user message but we didn't get any text
                    # from the STT (maybe the delay is so large that the audio finished
                    # before any text was received), set text_start
                    user_stopwatch.time_phase_if_not_started("text_start")

                user_messages = [m for m in chat_history if m["role"] == "user"]
                user_message = user_messages[-1]["content"] if user_messages else None
                receive_logger.info(
                    "Response created. User message: %s",
                    repr(user_message),
                )
                if user_message:
                    benchmark_chat_history.append(
                        BenchmarkUserMessage(
                            content=user_message,
                            timing=UserMessageTiming(**user_stopwatch.phase_dict()),
                        )
                    )
                    user_stopwatch.reset()
            elif isinstance(message, ora.UnmuteResponseTextDeltaReady):
                assistant_stopwatch.time_phase_if_not_started("text_start")
            elif isinstance(message, ora.ResponseAudioDelta):
                assistant_stopwatch.time_phase_if_not_started(
                    "audio_start",
                    # On rare occasions, the audio_start is before the text_start
                    check_previous=False,
                )

                base64_audio = message.delta
                binary_audio_data = base64.b64decode(base64_audio)
                pcm = opus_reader.append_bytes(binary_audio_data)

                if pcm.size:
                    current_audio_chunks.append(pcm)

            elif isinstance(message, ora.ResponseAudioDone):
                n_samples_received = sum(len(b) for b in current_audio_chunks)
                assistant_stopwatch.time_phase_if_not_started("audio_end")

                received_audio_length = n_samples_received / SAMPLE_RATE
                receive_logger.info("Message: %s", repr(chat_history[-1]["content"]))

                benchmark_chat_history.append(
                    BenchmarkAssistantMessage(
                        content=chat_history[-1]["content"],
                        timing=AssistantMessageTiming(
                            **assistant_stopwatch.phase_dict(),
                            received_audio_length=received_audio_length,
                        ),
                    )
                )
                assistant_stopwatch.reset()

                audio_file_data = random.choice(audio_files_data)
                await audio_to_emit.put(audio_file_data)
                user_stopwatch.time_phase_if_not_started("audio_start")

                # We know how long the audio is, so set the end time directly
                audio_file_length = audio_file_data.shape[0] / SAMPLE_RATE
                user_stopwatch.time_phase_if_not_started(
                    "audio_end",
                    t=user_stopwatch.times[0] + audio_file_length,
                    check_previous=False,
                )

                if listen:
                    preview_audio(
                        np.concatenate(current_audio_chunks), playback_speed=2.0
                    )

                current_audio_chunks = []
                if len(chat_history) >= MAX_N_MESSAGES:
                    break
            elif isinstance(message, ora.ConversationItemInputAudioTranscriptionDelta):
                user_stopwatch.time_phase_if_not_started("text_start")
            elif isinstance(message, ora.UnmuteAdditionalOutputs):
                chat_history = message.args["chat_history"]
            elif isinstance(
                message,
                (ora.ResponseTextDone, ora.SessionUpdated, ora.ResponseTextDelta),
            ):
                pass  # ignored message
            else:
                receive_logger.info(f"Received unknown message: {message}")

        await audio_to_emit.put(CloseStream())
    except websockets.ConnectionClosed as e:
        receive_logger.info(f"Connection closed while receiving messages: {e}")
        if e.code != websockets.CloseCode.NORMAL_CLOSURE:
            return e

    return benchmark_chat_history


def get_voice(server_url: str, basic_auth: tuple[str, str] | None) -> str:
    """Select the first voice that the backend tells us about."""

    voices = requests.get(
        ws_to_http(server_url) + "/v1/voices",
        auth=basic_auth,
    )
    voices.raise_for_status()

    voices = voices.json()
    voice = VoiceSample(**voices[0])

    path_on_server = voice.source.path_on_server
    assert path_on_server is not None
    return path_on_server


def check_health(server_url: str, basic_auth: tuple[str, str] | None):
    health_url = ws_to_http(server_url).strip("/") + "/v1/health"
    main_logger.info(f"Checking health at {health_url}")
    response = requests.get(health_url, auth=basic_auth)

    if response.status_code != 200:
        raise RuntimeError(f"Server is not healthy: {response.text}")

    health = response.json()
    if not health["ok"]:
        raise RuntimeError(f"Server is not healthy: {health}")


async def _main(
    audio_files_data: list[np.ndarray],
    server_url: str,
    basic_auth: tuple[str, str] | None,
    listen: bool,
) -> list[BenchmarkMessage] | BaseException:
    voice = get_voice(server_url, basic_auth)

    websocket_url = f"{server_url.strip('/')}/v1/realtime"
    async with websockets.connect(
        websocket_url,
        subprotocols=[websockets.Subprotocol("realtime")],
    ) as websocket:
        main_logger.info(f"Connected to {websocket_url}")
        audio_to_emit: asyncio.Queue[np.ndarray | CloseStream] = asyncio.Queue()

        emit_task = asyncio.create_task(emit_loop(websocket, audio_to_emit, voice))
        receive_task = asyncio.create_task(
            receive_loop(websocket, audio_to_emit, audio_files_data, listen=listen)
        )
        _, receive_report = await asyncio.gather(emit_task, receive_task)

        return receive_report


def main_one_worker(
    audio_files_data: list[np.ndarray],
    server_url: str,
    basic_auth: tuple[str, str] | None,
    listen: bool,
    catch_exceptions: bool = False,
    delay: float = 0.0,
) -> list[BenchmarkMessage] | BaseException:
    if delay > 0:
        time.sleep(delay)

    try:
        return asyncio.run(
            _main(audio_files_data, server_url, basic_auth, listen=listen)
        )
    except Exception as e:
        if not catch_exceptions:
            raise
        else:
            main_logger.error(f"Error in main_one_worker: {e}")
            return e


def distribution_stats(data: list[float]) -> dict[str, float]:
    """Calculate the mean, median, and standard deviation of a list of numbers."""
    if not data:
        return {"count": 0}

    return {
        "count": len(data),
        "mean": float(np.mean(data)),
        "median": float(np.median(data)),
        "p90": float(np.percentile(data, 90)),
        "p95": float(np.percentile(data, 95)),
    }


def main(
    audio_dir: Path,
    server_url: str,
    basic_auth: tuple[str, str] | None,
    listen: bool,
    n_workers: int = 1,
    n_conversations: int = 1,
):
    check_health(server_url, basic_auth)

    # For a more realistic load, not everyone starts at the same time
    DELAY_STEP = 2.0 / n_workers

    audio_files_data = []
    for audio_file in audio_dir.glob("*.mp3"):
        audio_file_data, _sr = sphn.read(audio_file, sample_rate=SAMPLE_RATE)
        audio_file_data = audio_file_data[0]  # Take first channel to make it mono
        audio_files_data.append(audio_file_data)

    with multiprocessing.Pool(n_workers) as pool:
        # Use starmap_async to allow for KeyboardInterrupt handling

        async_result = pool.starmap_async(
            main_one_worker,
            (
                (
                    audio_files_data,
                    server_url,
                    basic_auth,
                    listen,
                    True,
                    # If there are more tasks than workers, we don't want to keep
                    # increasing the delay, hence the modulo
                    DELAY_STEP * (i % n_workers),
                )
                for i in range(n_conversations)
            ),
        )
        reports: list[list[BenchmarkMessage] | BaseException]
        try:
            reports = async_result.get()  # Wait for all results
        except KeyboardInterrupt:
            print("KeyboardInterrupt detected. Fetching partial results...")
            reports = async_result._value  # type: ignore # Retrieve partial results
            reports: list[list[BenchmarkMessage] | BaseException] = [
                report if report is not None else KeyboardInterrupt()
                for report in reports
            ]

    valid_reports = [r for r in reports if not isinstance(r, BaseException)]
    print(json.dumps(valid_reports, indent=2, default=pydantic_encoder))

    print("Errors:", [r for r in reports if isinstance(r, BaseException)])

    report = combine_latency_reports([make_latency_report(r) for r in valid_reports])
    print(json.dumps(report, indent=2, default=pydantic_encoder))
    print(
        json.dumps(
            {
                "stt_latencies": distribution_stats(report.stt_latencies),
                "vad_latencies": distribution_stats(report.vad_latencies),
                "llm_latencies": distribution_stats(report.llm_latencies),
                "tts_start_latencies": distribution_stats(report.tts_start_latencies),
                "tts_realtime_factors": distribution_stats(report.tts_realtime_factors),
            },
            indent=2,
            default=pydantic_encoder,
        )
    )
    print(
        "OK fraction:",
        sum([int(not isinstance(r, Exception)) for r in reports]) / len(reports),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Load test client for the Unmute server."
    )
    parser.add_argument("--server-url", required=True, help="URL of the server.")
    parser.add_argument(
        "--audio-dir",
        type=Path,
        help="Directory containing the audio files. "
        "The loadtest assumes that speech starts *immediately* - otherwise the STT "
        "timing will be inaccurate.",
        default=Path(__file__).parent / "voices",
    )
    parser.add_argument(
        "--listen",
        action="store_true",
        help="Listen to the received audio.",
    )
    parser.add_argument(
        "--n-workers",
        type=int,
        default=1,
        help="How many workers in parallel to run.",
    )
    parser.add_argument(
        "--n-conversations",
        type=int,
        help="How many conversations to run in total. By default, equal to n_workers.",
    )
    parser.add_argument("--username", type=str, help="Username for HTTP basic auth.")
    parser.add_argument("--password", type=str, help="Password for HTTP basic auth.")

    args = parser.parse_args()

    basic_auth = (
        (args.username, args.password) if args.username and args.password else None
    )
    main(
        args.audio_dir,
        args.server_url,
        basic_auth,
        listen=args.listen,
        n_workers=args.n_workers,
        n_conversations=args.n_conversations or args.n_workers,
    )
