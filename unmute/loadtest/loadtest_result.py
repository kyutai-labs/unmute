from typing import Literal

import numpy as np
from pydantic import BaseModel, model_validator


class UserMessageTiming(BaseModel):
    audio_start: float
    text_start: float
    audio_end: float

    @model_validator(mode="after")
    def validate_timing(self):
        # Note that text_start and audio_end can be in either order
        if not (self.audio_start < self.text_start) or not (
            self.audio_start < self.audio_end
        ):
            raise ValueError(f"Invalid timing: {self}")
        return self


class AssistantMessageTiming(BaseModel):
    response_created: float
    text_start: float
    audio_start: float
    audio_end: float
    received_audio_length: float

    @model_validator(mode="after")
    def validate_timing(self):
        if not (self.response_created < self.audio_start < self.audio_end):
            raise ValueError(f"Invalid timing: {self}")
        return self


class BenchmarkUserMessage(BaseModel):
    role: Literal["user"] = "user"
    content: str
    timing: UserMessageTiming


class BenchmarkAssistantMessage(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    timing: AssistantMessageTiming


BenchmarkMessage = BenchmarkUserMessage | BenchmarkAssistantMessage


class LatencyReport(BaseModel):
    stt_latencies: list[float]
    vad_latencies: list[float]
    llm_latencies: list[float]
    tts_start_latencies: list[float]
    tts_realtime_factors: list[float]

    def compress(self):
        return LatencyReport(
            stt_latencies=[float(np.mean(self.stt_latencies))],
            vad_latencies=[float(np.mean(self.vad_latencies))],
            llm_latencies=[float(np.mean(self.llm_latencies))],
            tts_start_latencies=[float(np.mean(self.tts_start_latencies))],
            tts_realtime_factors=[float(np.mean(self.tts_realtime_factors))],
        )


def combine_latency_reports(reports: list[LatencyReport]) -> LatencyReport:
    return LatencyReport(
        stt_latencies=[lat for r in reports for lat in r.stt_latencies],
        vad_latencies=[lat for r in reports for lat in r.vad_latencies],
        llm_latencies=[lat for r in reports for lat in r.llm_latencies],
        tts_start_latencies=[lat for r in reports for lat in r.tts_start_latencies],
        tts_realtime_factors=[
            factor for r in reports for factor in r.tts_realtime_factors
        ],
    )


def make_latency_report(
    benchmark_chat_history: list[BenchmarkMessage],
) -> LatencyReport:
    stt_latencies = []
    vad_latencies = []
    llm_latencies = []
    tts_start_latencies = []
    tts_realtime_factors = []

    for i in range(len(benchmark_chat_history)):
        m = benchmark_chat_history[i]

        if isinstance(m, BenchmarkAssistantMessage):
            realtime_factor = m.timing.received_audio_length / (
                m.timing.audio_end - m.timing.audio_start
            )
            tts_realtime_factors.append(realtime_factor)
            llm_latencies.append(m.timing.text_start - m.timing.response_created)
            tts_start_latencies.append(m.timing.audio_start - m.timing.text_start)

            if i > 0:
                vad_latency = (
                    m.timing.response_created
                    - benchmark_chat_history[i - 1].timing.audio_end
                )
                vad_latencies.append(vad_latency)
        elif isinstance(m, BenchmarkUserMessage):  # type: ignore
            stt_latency = m.timing.text_start - m.timing.audio_start
            stt_latencies.append(stt_latency)

    return LatencyReport(
        stt_latencies=stt_latencies,
        vad_latencies=vad_latencies,
        llm_latencies=llm_latencies,
        tts_start_latencies=tts_start_latencies,
        tts_realtime_factors=tts_realtime_factors,
    )
