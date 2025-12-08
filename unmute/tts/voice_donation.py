import datetime
import functools
import logging
import random
import time
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from unmute import metrics as mt
from unmute.cache import get_cache
from unmute.kyutai_constants import MAX_VOICE_FILE_SIZE_MB, VOICE_DONATION_DIR

MINUTES_TO_VERIFY = 5
SECONDS_IN_HOUR = 60 * 60

voice_donation_verification_cache = get_cache(
    prefix="voice_donation_verification", ttl_seconds=SECONDS_IN_HOUR * 1
)

CONSTANT_PREFIX = "I consent to my voice being used for voice cloning."

logger = logging.getLogger(__name__)


@functools.cache
def get_sentences():
    with open(Path(__file__).parent / "voice_donation_sentences.txt", "r") as f:
        return [line.strip() for line in f if line.strip()]


class VoiceDonationVerification(BaseModel):
    id: str
    text: str
    created_at_timetamp: float  # seconds since epoch


def generate_verification() -> VoiceDonationVerification:
    sentences = get_sentences()
    chosen_sentences = random.sample(sentences, 2)
    verification_text = f"{CONSTANT_PREFIX} {chosen_sentences[0]} {chosen_sentences[1]}"
    verification_id = uuid.uuid4()

    verification = VoiceDonationVerification(
        id=str(verification_id),
        text=verification_text,
        created_at_timetamp=time.time(),
    )

    voice_donation_verification_cache.set(
        verification.id, verification.model_dump_json()
    )
    voice_donation_verification_cache.cleanup()

    return verification


class VoiceDonationSubmission(BaseModel):
    format_version: Literal["1.0", "1.1"] = "1.1"
    # The email is kept so that the person can contact us if they want to withdraw their
    # donation, not published.
    email: str
    nickname: str
    verification_id: uuid.UUID
    # Only CC0 is allowed for now, but storing in case we decide to change it later
    license: Literal["CC0"] = "CC0"
    # The transcription is sent by the client, so it could be manipulated
    transcription_from_client: str | None = None


class VoiceDonationMetadata(BaseModel):
    submission: VoiceDonationSubmission
    verification: VoiceDonationVerification
    timestamp: float
    timestamp_str: str  # For human readability


def submit_voice_donation(
    submission: VoiceDonationSubmission, audio_file: bytes
) -> None:
    file_size_mb = len(audio_file) / (1024 * 1024)

    # No way they would be able to say all verification sentences in this time.
    if file_size_mb < 0.1:
        raise ValueError("Audio file is too small. Please provide a valid audio file.")

    # Should be checked by middleware already, but let's ensure it here too
    if file_size_mb > MAX_VOICE_FILE_SIZE_MB:
        raise ValueError(
            f"Audio file is too large. Maximum size is {MAX_VOICE_FILE_SIZE_MB} MB."
        )

    if len(submission.nickname) > 30:
        raise ValueError("Nickname is too long. Maximum length is 30 characters.")

    verification_raw = voice_donation_verification_cache.get(
        str(submission.verification_id)
    )
    if not verification_raw:
        raise ValueError(
            "Couldn't find verification data for the provided ID. "
            "Note you must complete the verification within "
            f"{MINUTES_TO_VERIFY:.0f} minutes."
        )
    verification = VoiceDonationVerification.model_validate_json(verification_raw)

    sec_since_creation = time.time() - verification.created_at_timetamp

    if sec_since_creation > MINUTES_TO_VERIFY * 60:
        raise ValueError(
            f"Verification expired after {MINUTES_TO_VERIFY} minutes. "
            "Please request a new verification."
        )

    VOICE_DONATION_DIR.mkdir(parents=True, exist_ok=True)
    audio_file_path = VOICE_DONATION_DIR / f"{submission.verification_id}.wav"
    audio_file_path.write_bytes(audio_file)

    now = datetime.datetime.now().astimezone()
    metadata = VoiceDonationMetadata(
        submission=submission,
        verification=verification,
        timestamp=now.timestamp(),
        timestamp_str=now.isoformat(),
    )
    metadata_path = VOICE_DONATION_DIR / f"{submission.verification_id}.json"
    metadata_path.write_text(metadata.model_dump_json(indent=2))

    voice_donation_verification_cache.delete(str(submission.verification_id))
    voice_donation_verification_cache.cleanup()

    logger.info(
        f"Received voice donation with id {submission.verification_id}, "
        f"file size {file_size_mb:.2f} MB. "
        f"Saved to {audio_file_path}."
    )
    mt.VOICE_DONATION_SUBMISSIONS.inc()
