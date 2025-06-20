# https://github.com/gabrielchua/async-stream-openai-st/blob/824eab8f3ab600d3689d8d946526e48e0e0310c2/app.py
# https://qwen.readthedocs.io/en/latest/deployment/vllm.html#openai-compatible-api-service

from typing import Any, cast

from unmute.kyutai_constants import LLM_SERVER
from unmute.llm.llm_utils import VLLMStream, get_openai_client, rechunk_to_words

# Predefined message
PREDEFINED_MESSAGE = "Explain the second law of thermodynamics"


async def main(server_url: str):
    client = get_openai_client(server_url=server_url)
    s = VLLMStream(client)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {
            "role": "user",
            "content": f"Write a {200} word essay on 'bear vs shark'. "
            "The first line is a 2-3 word title with an emoji and then include "
            "2 line breaks. For example 'TITLE <emoji> \n \n ' ",
        },
    ]

    async for message in rechunk_to_words(s.chat_completion(cast(Any, messages))):
        print(message, end="", flush=True)

    print()


if __name__ == "__main__":
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(description="Run VLLM wrapper example.")
    parser.add_argument(
        "--server-url",
        type=str,
        default=LLM_SERVER,
        help=f"The URL of the VLLM server (default: {LLM_SERVER}).",
    )
    args = parser.parse_args()

    asyncio.run(main(args.server_url))
