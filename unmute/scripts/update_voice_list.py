"""Upload local voices to the server based on the voice list."""

import asyncio
import logging

from unmute.tts.voices import VoiceList


async def main():
    logging.basicConfig(level=logging.INFO)

    voice_list = VoiceList()
    await voice_list.upload_to_server()
    voice_list.save()
    print("Voices updated successfully. Voice list path:")
    print(voice_list.path)


if __name__ == "__main__":
    asyncio.run(main())
