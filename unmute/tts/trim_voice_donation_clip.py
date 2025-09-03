import argparse
from pathlib import Path

import numpy as np
import sphn

from unmute.kyutai_constants import SAMPLE_RATE


def trim_silence_end(
    audio: np.ndarray, threshold_db: float = -24.0, min_silence_sec: float = 1.0
) -> np.ndarray:
    """
    Trim silence from the end of the audio. Silence is defined as samples below a threshold (in dB relative to peak).
    """
    # Only operate on mono audio
    if audio.ndim != 1:
        raise ValueError("trim_silence_end expects mono audio (1D array)")

    peak = np.max(np.abs(audio))
    if peak == 0:
        return audio  # silent audio

    threshold = peak * 10 ** (threshold_db / 20)
    window_sec = 0.1
    window_size = int(window_sec * SAMPLE_RATE)
    if window_size < 1:
        window_size = 1

    # Compute moving RMS (root mean square) over the window
    def moving_rms(x: np.ndarray, w: int) -> np.ndarray:
        # Pad with zeros at the end to keep length
        if x.shape[0] < w:
            return np.array([])
        cumsum = np.cumsum(np.insert(x**2, 0, 0))
        rms = np.sqrt((cumsum[w:] - cumsum[:-w]) / w)
        # Pad to match input length (pad end)
        pad = np.zeros(x.shape[0] - rms.shape[0])
        return np.concatenate([rms, pad])

    rms = moving_rms(audio, window_size)
    # Find last window above threshold
    for i in range(rms.shape[0] - 1, -1, -1):
        if rms[i] > threshold:
            end = min(
                i + window_size + int(min_silence_sec * SAMPLE_RATE), audio.shape[0]
            )
            if end < audio.shape[0]:
                print(
                    "Trimming silence from end: "
                    f"{(audio.shape[0] - end) / SAMPLE_RATE:.1f}s removed"
                )
            return audio[:end]

    raise ValueError("Internal error, no windows above threshold found.")


def trim_trailing_silence(in_path: Path, out_path: Path | None = None) -> None:
    if out_path is None:
        out_path = in_path.with_stem(in_path.stem + "_trimmed")

    data, _sr = sphn.read(in_path, sample_rate=SAMPLE_RATE)

    if data.ndim == 2:
        data = np.mean(data, axis=0)
    elif data.ndim == 1:
        pass
    else:
        raise ValueError(f"Unexpected audio shape: {data.shape}")

    n_samples = data.shape[0]

    ten_sec_samples = int(SAMPLE_RATE * 10)
    if n_samples < ten_sec_samples:
        print(
            f"{in_path} is shorter than 10 seconds: "
            f"{n_samples / SAMPLE_RATE:.2f}s, not trimming"
        )
        sphn.write_wav(out_path, data, SAMPLE_RATE)
        return

    data = trim_silence_end(data)

    data_last10 = data[-ten_sec_samples:]
    if data_last10.shape[0] < ten_sec_samples:
        raise ValueError(
            "Less than 10 seconds remain after trimming silence: "
            f"{data_last10.shape[0] / SAMPLE_RATE:.2f}s"
        )

    sphn.write_wav(out_path, data_last10, SAMPLE_RATE)
    print(f"Wrote {out_path} ({data_last10.shape[0] / SAMPLE_RATE:.2f}s)")


def main():
    parser = argparse.ArgumentParser(
        description="Trim last 10s and trailing silence from wav files."
    )
    parser.add_argument(
        "inputs", nargs="+", help="Input wav files or glob patterns (e.g. *.wav)"
    )
    args = parser.parse_args()

    for arg in args.inputs:
        in_path = Path(arg)

        # if already trimmed, skip
        if in_path.suffix == ".wav" and in_path.stem.endswith("_trimmed"):
            print(f"Skipping {in_path} (already trimmed)")
            continue

        if not in_path.is_file():
            print(f"Skipping {in_path} (not a file)")
            continue
        try:
            trim_trailing_silence(in_path)
        except ValueError as e:
            print(f"Error processing {in_path}: {e}")
            continue


if __name__ == "__main__":
    main()
