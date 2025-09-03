import argparse
import csv
import os
from pathlib import Path

from unmute.tts.voice_donation import VoiceDonationMetadata


def get_flattened_donation(donation: VoiceDonationMetadata) -> dict:
    """Flatten the VoiceDonationMetadata for easier processing."""
    return {
        "verification_id": str(donation.submission.verification_id),
        "timestamp_str": donation.timestamp_str,
        "email": donation.submission.email,
        "nickname": donation.submission.nickname,
        "verification_text": donation.verification.text,
    }


def main(voice_donation_dir: Path, set_mtime: bool = False):
    backups = sorted(list(voice_donation_dir.glob("voice-donation_*/")))
    if not backups:
        print("No backups found.")
        exit(1)

    backup = backups[-1]
    print(f"Using backup: {backup}")

    donations: list[VoiceDonationMetadata] = []
    for donation_json in backup.glob("*.json"):
        with open(donation_json, "r") as f:
            metadata = VoiceDonationMetadata.model_validate_json(f.read())
            donations.append(metadata)

        if set_mtime:
            os.utime(donation_json, (metadata.timestamp, metadata.timestamp))
            donation_wav = donation_json.with_suffix(".wav")
            if not donation_wav.exists():
                print(f"Warning: {donation_wav} does not exist, skipping mtime set.")
            else:
                os.utime(donation_wav, (metadata.timestamp, metadata.timestamp))

    donations.sort(key=lambda x: x.timestamp)

    seen_nicknames = set()
    for donation in donations:
        if donation.submission.nickname in seen_nicknames:
            raise ValueError(
                f"Duplicate nickname found: {donation.submission.nickname}"
            )

        assert donation.submission.license == "CC0", "Only CC0 license expected"
        assert donation.submission.format_version == "1.0", (
            "Only format version 1.0 expected"
        )

    flattened_donations = [get_flattened_donation(d) for d in donations]

    output_tsv = voice_donation_dir / "flattened_donations.tsv"
    if flattened_donations:
        with open(output_tsv, "w", newline="") as tsvfile:
            writer = csv.DictWriter(
                tsvfile, fieldnames=flattened_donations[0].keys(), delimiter="\t"
            )
            writer.writeheader()
            writer.writerows(flattened_donations)
        print(f"Exported {len(flattened_donations)} donations to {output_tsv}")
        print(
            "You can copy this file and use cmd+shift+v to paste the values into a spreadsheet."
        )
    else:
        print("No donations to export.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process voice donation backups.")
    parser.add_argument(
        "voice_donation_dir",
        type=Path,
        help="Directory containing voice donation backups.",
    )
    parser.add_argument(
        "--set-mtime",
        action="store_true",
        help="Set modification time of each file to match its timestamp. "
        "Useful to be able to sort the folder by timestamp for manual verification, "
        "so that the file order matches the table.",
    )
    args = parser.parse_args()

    main(args.voice_donation_dir, set_mtime=args.set_mtime)
