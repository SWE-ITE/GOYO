"""
Simple harness to compare raw reference playback and FxLMS ANC with a saved secondary path.

Edit the configuration constants below, then run from the repo root:
    python -m ANC.ANC_test
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

import numpy as np
import pyaudio  # type: ignore

from fxlms_controller import DEFAULT_BLOCK_SIZE, FxLMSANC, read_mono_wav

# ---------------------------------------------------------------------------
# Configuration (adjust for your setup)
# ---------------------------------------------------------------------------
REFERENCE_PATH = Path(__file__).resolve().parent / "src/sine_200Hz.wav"
SECONDARY_PATH = Path(__file__).resolve().parent / "secondary_path.npy"

CONTROL_DEVICE = 3          # Output device index for the stereo speaker
RECORD_DEVICE = 1           # Input device index for the error microphone
REFERENCE_DEVICE: Optional[int] = None  # Separate speaker when not splitting channels

SPLIT_REFERENCE_CHANNELS = True  # Left = reference, right = anti-noise
STEP_SIZE = 1e-4
BLOCK_SIZE: Optional[int] = None  # None uses controller default
FILTER_LENGTH: Optional[int] = None  # None uses controller default
DURATION: Optional[float] = None  # Seconds; None runs until Ctrl+C

# Choose between "anc" for adaptive cancellation or "reference" for raw playback.
MODE = "r"  # "anc" or "reference"

# ---------------------------------------------------------------------------


def load_secondary_path(path: Path) -> np.ndarray:
    if not path.exists():
        raise FileNotFoundError(f"Secondary path file not found: {path}")
    taps = np.load(path)
    if taps.ndim != 1:
        raise ValueError("Secondary path taps must be a 1-D array")
    return taps.astype(np.float32)


def validate_config() -> None:
    if MODE not in {"a", "r"}:
        raise ValueError(f"Unsupported MODE '{MODE}'. Use 'anc' or 'reference'.")
    if CONTROL_DEVICE is None:
        raise ValueError("CONTROL_DEVICE must be set.")
    if MODE == "a" and RECORD_DEVICE is None:
        raise ValueError("RECORD_DEVICE must be set when MODE == 'anc'.")
    if SPLIT_REFERENCE_CHANNELS and REFERENCE_DEVICE is not None:
        raise ValueError("REFERENCE_DEVICE must be None when SPLIT_REFERENCE_CHANNELS is True.")
    if BLOCK_SIZE is not None and BLOCK_SIZE <= 0:
        raise ValueError("BLOCK_SIZE must be positive.")
    if FILTER_LENGTH is not None and FILTER_LENGTH <= 0:
        raise ValueError("FILTER_LENGTH must be positive.")


def run_anc() -> None:
    taps = load_secondary_path(SECONDARY_PATH)

    init_kwargs = {
        "reference_path": str(REFERENCE_PATH),
        "secondary_path": taps,
        "control_device_index": CONTROL_DEVICE,
        "record_device_index": RECORD_DEVICE,
        "reference_device_index": REFERENCE_DEVICE,
        "play_reference": True,  # Ensure reference stays audible during ANC
        "step_size": STEP_SIZE,
        "split_reference_channels": SPLIT_REFERENCE_CHANNELS,
    }
    if BLOCK_SIZE is not None:
        init_kwargs["block_size"] = BLOCK_SIZE
    if FILTER_LENGTH is not None:
        init_kwargs["filter_length"] = FILTER_LENGTH

    controller = FxLMSANC(**init_kwargs)

    def log_metrics(metrics) -> None:
        logging.info("frame=%05d error_rms=%.6f", metrics.frame_index, metrics.error_rms)

    logging.info("Starting ANC session (Ctrl+C to stop).")
    try:
        controller.run(loop_reference=DURATION is None, max_duration=DURATION, metrics_callback=log_metrics)
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")


def play_reference_only() -> None:
    signal, sample_rate = read_mono_wav(str(REFERENCE_PATH))
    loop_reference = DURATION is None
    block_len = BLOCK_SIZE if BLOCK_SIZE is not None else DEFAULT_BLOCK_SIZE

    pa = pyaudio.PyAudio()
    control_stream = pa.open(
        format=pyaudio.paFloat32,
        channels=2 if SPLIT_REFERENCE_CHANNELS else 1,
        rate=sample_rate,
        output=True,
        frames_per_buffer=block_len,
        output_device_index=CONTROL_DEVICE,
    )
    reference_stream = None
    if REFERENCE_DEVICE is not None:
        reference_stream = pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=sample_rate,
            output=True,
            frames_per_buffer=block_len,
            output_device_index=REFERENCE_DEVICE,
        )

    index = 0
    start_time = time.time()
    try:
        while True:
            if DURATION is not None and (time.time() - start_time) >= DURATION:
                break

            block = signal[index : index + block_len]
            if len(block) == 0:
                break
            if len(block) < block_len:
                block = np.pad(block, (0, block_len - len(block))).astype(np.float32)

            if SPLIT_REFERENCE_CHANNELS:
                stereo = np.zeros(block_len * 2, dtype=np.float32)
                stereo[0::2] = block
                control_stream.write(stereo.tobytes())
            else:
                control_stream.write(block.astype(np.float32).tobytes())

            if reference_stream is not None:
                reference_stream.write(block.astype(np.float32).tobytes())

            index += block_len
            if index >= len(signal):
                if loop_reference:
                    index = 0
                else:
                    break
    finally:
        control_stream.stop_stream()
        control_stream.close()
        if reference_stream:
            reference_stream.stop_stream()
            reference_stream.close()
        pa.terminate()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    validate_config()

    if MODE == "a":
        run_anc()
    else:
        play_reference_only()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
