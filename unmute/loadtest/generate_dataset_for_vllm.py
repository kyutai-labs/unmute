"""Generate data for benchmarking with vLLM's benchmark_serving.py.

See:
https://github.com/vllm-project/vllm/tree/main/benchmarks
"""

import json
import random

from unmute.tts.voices import VoiceList


def random_id():
    return "".join(random.choices("1234567890", k=8))


METATEMPLATE = "<bos><start_of_turn>user{system_prompt}\n\n\nHello!<end_of_turn>\n<start_of_turn>model\n"


def main():
    voice_list = VoiceList()
    possible_instructions = [
        v.instructions for v in voice_list.voices if v.instructions is not None
    ]

    prompts = []

    for _ in range(10000):
        instructions = random.choice(possible_instructions)

        # This will lead to some amount of kv-caching because the system prompts have
        # common prefixes. But some of the dynamic prompts will be changing so that
        # will break the cache at the point where they differ, which should lead to
        # a realistic load.
        system_prompt = instructions.make_system_prompt()
        full_prompt = METATEMPLATE.format(system_prompt=system_prompt)
        prompts.append(full_prompt)

    s = json.dumps(
        [
            {
                "id": random_id(),
                "conversations": [
                    {
                        "from": "human",
                        "value": full_prompt,
                    },
                    # The vLLM benchmark script looks at the length of the response to
                    # know how many tokens to generate. This seems like a reasonable
                    # length of the response
                    {
                        "from": "gpt",
                        "value": "Here are the main ideas of Jeff Walker's Product Launch Formula that can be applied by a growth marketing agency for their clients.",
                    },
                ],
            }
            for full_prompt in prompts
        ],
        indent=2,
    )
    print(s)


if __name__ == "__main__":
    main()
