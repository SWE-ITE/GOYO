"""
Play the reference noise alone for a short preview, then switch to ANC.

Configuration below is hard-coded; adjust to match your setup and run:
    python -m ANC.reference_then_anc
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
# Configuration
# ---------------------------------------------------------------------------
REFERENCE_PATH = Path(__file__).resolve().parent / "src/sine_200Hz.wav"
SECONDARY_PATH = Path(__file__).resolve().parent / "secondary_path.npy"

CONTROL_DEVICE = 3
RECORD_DEVICE = 1
REFERENCE_DEVICE: Optional[int] = None

SPLIT_REFERENCE_CHANNELS = True  # Left = reference, right = anti-noise
STEP_SIZE = 1e-4
BLOCK_SIZE: Optional[int] = None
FILTER_LENGTH: Optional[int] = None

REFERENCE_PREVIEW_SECONDS = 3.0
ANC_DURATION: Optional[float] = None  # None = run until Ctrl+C after preview
# ---------------------------------------------------------------------------


def play_reference_preview() -> None:
    signal, sample_rate = read_mono_wav(str(REFERENCE_PATH))
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
        while time.time() - start_time < REFERENCE_PREVIEW_SECONDS:
            block = signal[index : index + block_len]
            if len(block) == 0:
                index = 0
                continue
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
                index = 0
    finally:
        control_stream.stop_stream()
        control_stream.close()
        if reference_stream:
            reference_stream.stop_stream()
            reference_stream.close()
        pa.terminate()


def run_anc() -> None:
    taps = np.load(SECONDARY_PATH)
    init_kwargs = {
        "reference_path": str(REFERENCE_PATH),
        "secondary_path": taps,
        "control_device_index": CONTROL_DEVICE,
        "record_device_index": RECORD_DEVICE,
        "reference_device_index": REFERENCE_DEVICE,
        "play_reference": True,
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
        controller.run(loop_reference=ANC_DURATION is None, max_duration=ANC_DURATION, metrics_callback=log_metrics)
    except KeyboardInterrupt:
        logging.info("ANC stopped by user.")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.info("Playing reference preview for %.1f seconds.", REFERENCE_PREVIEW_SECONDS)
    play_reference_preview()
    logging.info("Preview finished. Switching to ANC...")
    run_anc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
