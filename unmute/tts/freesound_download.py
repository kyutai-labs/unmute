import argparse
import logging
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Literal

import requests
import tqdm
from pydantic import BaseModel, Field
from ruamel.yaml import YAML

logger = logging.getLogger(__name__)


class SoundPreviews(BaseModel):
    preview_hq_mp3: str
    preview_lq_mp3: str
    preview_hq_ogg: str
    preview_lq_ogg: str

    # The JSONs have dashes instead of underscores
    model_config = {
        "populate_by_name": True,
        "alias_generator": lambda field_name: field_name.replace("_", "-"),
    }


def to_filename_friendly(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s)  # Remove all special characters
    s = re.sub(r"\s+", "-", s)  # Replace spaces with dashes
    return s.lower()


class FreesoundSoundInstance(BaseModel):
    """See https://freesound.org/docs/api/resources_apiv2.html#sound-instance"""

    id: int
    name: str
    username: str
    previews: SoundPreviews | None = Field(default=None, exclude=True)
    license: str

    def get_filename(self) -> str:
        filename_friendly_name = to_filename_friendly(self.name)
        return f"{self.id}_{filename_friendly_name}.mp3"


class FreesoundVoiceSource(BaseModel):
    source_type: Literal["freesound"] = "freesound"
    url: str
    start_time: int | None = None
    sound_instance: FreesoundSoundInstance | None = None
    path_on_server: str


def get_sound_id_from_url(url: str) -> int:
    # e.g. https://freesound.org/people/balloonhead/sounds/785958/
    matches = re.search(r"/sounds/(\d+)/", url)
    if matches is None:
        raise ValueError(f"Invalid Freesound URL: {url}")

    return int(matches.group(1))


def get_sound_instance(sound_id_or_url: int | str) -> FreesoundSoundInstance:
    if isinstance(sound_id_or_url, int):
        sound_id = sound_id_or_url
    else:
        sound_id = get_sound_id_from_url(sound_id_or_url)

    response = requests.get(
        f"https://freesound.org/apiv2/sounds/{sound_id}/",
        headers={"Authorization": f"Token {os.environ['FREESOUND_API_KEY']}"},
    )
    response.raise_for_status()

    return FreesoundSoundInstance(**response.json())


def process_sound(input_path: Path, output_path: Path, start_time: int):
    with tempfile.NamedTemporaryFile(suffix=".mkv", delete=False) as temp_file:
        temp_path = Path(temp_file.name)

        volume_normalization_result = subprocess.run(
            [
                # This binary should be available because ffmpeg-normalize is a dev
                # dependency. Running via `uv run` should make it available.
                "ffmpeg-normalize",
                "-f",  # overwrite, because the tempfile already exists
                input_path,
                "-o",
                temp_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if volume_normalization_result.returncode != 0:
            print(volume_normalization_result.stderr.decode("utf-8"))
            raise RuntimeError("ffmpeg-normalize failed")

        result = subprocess.run(
            [
                "ffmpeg",
                "-i",
                temp_path,
                "-ss",
                str(start_time),
                "-t",  # take 10 seconds
                "10",
                "-ac",  # make it mono
                "1",
                "-af",  # resample to 24kHz, pad to 10 seconds if needed
                "apad=pad_dur=10,aresample=24000",
                "-ar",  # set sample rate (not sure why needed twice)
                "24000",
                "-y",  # overwrite output file if it exists
                output_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            print(result.stderr.decode("utf-8"))
            raise RuntimeError("FFmpeg failed")


repo_root = Path(__file__).parents[2]
OUTPUT_DIR = repo_root / "voices"

ALLOWED_LICENSES = [
    "http://creativecommons.org/publicdomain/zero/1.0/",  # CC0 1.0
    "https://creativecommons.org/licenses/by/4.0/",  # CC-BY 4.0
    "http://creativecommons.org/licenses/by/3.0/",  # CC-BY 3.0
]


def download_sound(source: FreesoundVoiceSource | str):
    if isinstance(source, str):
        source = FreesoundVoiceSource(url=source, path_on_server="filled in later")
    else:
        source = deepcopy(source)

    # We need to load this even if we have a sound instance already, because we don't
    # serialize the links to the previews
    sound_instance = get_sound_instance(source.url)

    assert sound_instance.previews is not None, (
        f"Sound instance has no previews: {sound_instance}"
    )

    if sound_instance.license not in ALLOWED_LICENSES:
        raise ValueError(
            f"Sound {sound_instance.id} has license {sound_instance.license}, "
            f"but only {ALLOWED_LICENSES} are allowed"
        )

    (OUTPUT_DIR / "raw").mkdir(exist_ok=True, parents=True)
    (OUTPUT_DIR / "voices" / "unmute-prod-website").mkdir(exist_ok=True, parents=True)

    # Cache the raw file to avoid downloading it again
    raw_path = OUTPUT_DIR / "raw" / sound_instance.get_filename()
    if not raw_path.exists():
        response = requests.get(sound_instance.previews.preview_hq_mp3)
        response.raise_for_status()
        with raw_path.open("wb") as f:
            f.write(response.content)

    output_path = (
        OUTPUT_DIR / "voices" / "unmute-prod-website" / sound_instance.get_filename()
    )
    if not output_path.exists():
        process_sound(raw_path, output_path, start_time=source.start_time or 0)

    source.sound_instance = sound_instance
    source.path_on_server = str(
        Path("unmute-prod-website/freesound") / sound_instance.get_filename()
    )

    return output_path, source


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "input_file", type=Path, help="YAML file describing what do download"
    )
    args = parser.parse_args()
    input_file = args.input_file

    OUTPUT_DIR.mkdir(exist_ok=True)

    with input_file.open() as f:
        sounds = YAML().load(f)
        sounds = [FreesoundVoiceSource(**sound) for sound in sounds]

    downloaded_paths = []
    for sound in (pbar := tqdm.tqdm(sounds)):
        pbar.set_description(sound.url)
        downloaded_paths.append(download_sound(sound))

    print("Downloaded to the following paths:")
    for path in downloaded_paths:
        print(path)
