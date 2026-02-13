import argparse
import csv
from pathlib import Path

from unmute.tts.trim_voice_donation_clip import trim_trailing_silence


def main():
    parser = argparse.ArgumentParser(
        description="Copy approved voice donation .wav files with proper naming."
    )
    parser.add_argument(
        "--table",
        required=True,
        help="Path to the .tsv or .csv file with metadata.",
        type=Path,
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing input .wav files named {verification_id}.wav",
        type=Path,
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory to copy approved .wav files to.",
        type=Path,
    )
    args = parser.parse_args()

    # Detect delimiter
    table_path = Path(args.table)
    delimiter = "\t" if table_path.suffix.lower() == ".tsv" else ","

    # Ask for confirmation before clearing the output directory
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        confirm = (
            input(
                f"Output directory {args.output_dir} is not empty. "
                "Will clear .wav and .wav.safetensors files (except for _enhanced.wav) "
                "before continuing. "
                "Ok? (y/N): "
            )
            .strip()
            .lower()
        )
        if confirm != "y":
            print("Exiting.")
            exit(1)

        for item in args.output_dir.iterdir():
            if (
                item.is_file()
                and (item.suffix == ".wav" or item.name.endswith(".wav.safetensors"))
                and not item.name.endswith("_enhanced.wav")
            ):
                item.unlink()

    with table_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            approval = row.get("approval", "").strip().upper()
            if approval != "TRUE":
                continue

            verification_id = row["verification_id"].strip()

            in_path = args.input_dir / f"{verification_id}.wav"

            if not in_path.is_file():
                raise FileNotFoundError(f"Input file not found: {in_path}")

            nickname_override = row.get("nickname override", "").strip()
            nickname = row.get("nickname", "").strip()
            if nickname_override:
                out_name = nickname_override
            elif nickname:
                out_name = nickname
            else:
                out_name = verification_id[:4]

            # Clean output name
            out_name = (
                out_name.replace(".", " ")
                .replace("/", " ")
                .replace("\\", " ")
                .strip()  # Strip trailing spaces before turning them into underscores
                .replace(" ", "_")
            )
            out_path = args.output_dir / f"{out_name}.wav"

            trim_trailing_silence(in_path, out_path)
            print(f"Copied {in_path} -> {out_path}, trimming silence")


if __name__ == "__main__":
    main()
