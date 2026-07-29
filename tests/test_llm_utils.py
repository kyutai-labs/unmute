from types import SimpleNamespace, TracebackType
from typing import Any, cast

import pytest
from openai import AsyncOpenAI

from unmute.llm import llm_utils
from unmute.llm.llm_utils import (
    VLLMStream,
    preprocess_messages_for_llm,
    rechunk_to_words,
)


class FakeCompletionStream:
    def __init__(self):
        self.sent = False

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ):
        return None

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.sent:
            raise StopAsyncIteration
        self.sent = True
        return SimpleNamespace(
            choices=[SimpleNamespace(delta=SimpleNamespace(content="hello"))]
        )


class FakeCompletions:
    def __init__(self):
        self.requests: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any):
        self.requests.append(kwargs)
        return FakeCompletionStream()


class FakeOpenAI:
    def __init__(self):
        self.chat = SimpleNamespace(completions=FakeCompletions())


async def make_iterator(s: str):
    parts = s.split("|")
    for part in parts:
        yield part


@pytest.mark.asyncio
async def test_vllm_stream_disables_model_thinking_when_configured(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(llm_utils, "autoselect_model", lambda: "test-model")
    client = FakeOpenAI()
    llm = VLLMStream(cast(AsyncOpenAI, client), enable_thinking=False)

    response = [
        part
        async for part in llm.chat_completion(
            [{"role": "user", "content": "Say hello."}]
        )
    ]

    assert response == ["hello"]
    assert client.chat.completions.requests == [
        {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Say hello."}],
            "stream": True,
            "temperature": 1.0,
            "extra_body": {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                }
            },
        }
    ]


@pytest.mark.asyncio
async def test_vllm_stream_leaves_backend_request_unchanged_by_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(llm_utils, "autoselect_model", lambda: "test-model")
    client = FakeOpenAI()
    llm = VLLMStream(cast(AsyncOpenAI, client))

    response = [
        part
        async for part in llm.chat_completion(
            [{"role": "user", "content": "Say hello."}]
        )
    ]

    assert response == ["hello"]
    assert client.chat.completions.requests == [
        {
            "model": "test-model",
            "messages": [{"role": "user", "content": "Say hello."}],
            "stream": True,
            "temperature": 1.0,
        }
    ]


@pytest.mark.asyncio
async def test_rechunk_to_words():
    test_strings = [
        "hel|lo| |w|orld",
        "hello world",
        "hello \nworld",
        "hello| |world",
        "hello| |world|.",
        "h|e|l|l|o| |\tw|o|r|l|d|.",
        "h|e|l|l|o\n| |w|o|r|l|d|.",
    ]

    for s in test_strings:
        parts = [x async for x in rechunk_to_words(make_iterator(s))]
        assert parts[0] == "hello"
        assert parts[1] == " world" or parts[1] == " world."

    async def f(s: str):
        x = [x async for x in rechunk_to_words(make_iterator(s))]
        print(x)
        return x

    assert await f("i am ok") == ["i", " am", " ok"]
    assert await f(" i am ok") == [" i", " am", " ok"]
    assert await f(" they are ok") == [" they", " are", " ok"]
    assert await f("  foo bar") == [" foo", " bar"]
    assert await f(" \t foo  bar") == [" foo", " bar"]


def test_preprocess_messages_for_llm_removes_user_silence_marker_from_output_only():
    chat_history = [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "...hello again"},
        {"role": "assistant", "content": "Sure."},
    ]

    processed = preprocess_messages_for_llm(chat_history)

    assert processed[1]["content"] == "hello again"
    # Ensure the original chat history is not mutated.
    assert chat_history[1]["content"] == "...hello again"
