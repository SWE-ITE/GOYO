"""
Live microphone monitor for the configured ANC inputs.

This opens the devices configured in ``ANC.real-time_ANC.realtime_cli`` and shows
two live time-domain plots:
  - Error mic (from RECORD_DEVICE, channel ERROR_INPUT_CHANNEL)
  - Reference mic (from RECORD_DEVICE reference channel, or a dedicated
    REFERENCE_INPUT_DEVICE if configured)

Usage:
    python -m ANC.utils.mictest
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import pyaudio  # type: ignore

from ANC.realtime_ANC import realtime_cli


def _open_stream(
    pa: pyaudio.PyAudio, device_index: int, channels: int, rate: int, frames_per_buffer: int
) -> pyaudio.Stream:
    return pa.open(
        format=pyaudio.paInt16,
        channels=channels,
        rate=rate,
        input=True,
        frames_per_buffer=frames_per_buffer,
        input_device_index=device_index,
    )


def _extract_channels(
    block: np.ndarray, channels: int
) -> np.ndarray:
    frames = np.frombuffer(block, dtype=np.int16).astype(np.float32) / 32768.0
    return frames.reshape(-1, channels)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    record_device = realtime_cli.RECORD_DEVICE
    ref_input_device = realtime_cli.REFERENCE_INPUT_DEVICE
    err_ch = realtime_cli.ERROR_INPUT_CHANNEL
    ref_ch = realtime_cli.REFERENCE_INPUT_CHANNEL
    sample_rate = realtime_cli.REFERENCE_SAMPLE_RATE or 16_000
    block_size = realtime_cli.BLOCK_SIZE or 1024

    if record_device is None:
        raise ValueError("Set RECORD_DEVICE in realtime_cli.py before running this monitor.")

    record_channels = max(err_ch, ref_ch if ref_ch is not None else 0) + 1

    pa = pyaudio.PyAudio()
    record_stream = _open_stream(pa, record_device, record_channels, sample_rate, block_size)
    ref_stream: Optional[pyaudio.Stream] = None
    if ref_input_device is not None:
        ref_stream = _open_stream(pa, ref_input_device, 1, sample_rate, block_size)

    plt.ion()
    fig, (ax_err, ax_ref) = plt.subplots(2, 1, num="Mic Test (error/ref)")
    err_line, = ax_err.plot([], [], lw=1)
    ref_line, = ax_ref.plot([], [], lw=1)

    ax_err.set_title("Error mic")
    ax_ref.set_title("Reference mic")
    for ax in (ax_err, ax_ref):
        ax.set_ylim(-1.1, 1.1)
        ax.set_xlim(0, block_size)
        ax.grid(True, which="both", linestyle="--", alpha=0.4)

    logging.info("Monitoring mics (Ctrl+C to stop). record_device=%s ref_device=%s", record_device, ref_input_device)
    try:
        while True:
            raw = record_stream.read(block_size, exception_on_overflow=False)
            frames = _extract_channels(raw, record_channels)
            err_sig = frames[:, err_ch]

            if ref_stream is not None:
                raw_ref = ref_stream.read(block_size, exception_on_overflow=False)
                ref_sig = _extract_channels(raw_ref, 1)[:, 0]
            elif ref_ch is not None and ref_ch < record_channels:
                ref_sig = frames[:, ref_ch]
            else:
                ref_sig = np.zeros_like(err_sig)

            x_axis = np.arange(len(err_sig))
            err_line.set_data(x_axis, err_sig)
            ref_line.set_data(x_axis, ref_sig)
            for ax in (ax_err, ax_ref):
                ax.set_xlim(0, len(err_sig))
            fig.canvas.draw()
            fig.canvas.flush_events()
            plt.pause(0.001)
    except KeyboardInterrupt:
        logging.info("Stopping mic monitor.")
    finally:
        record_stream.stop_stream()
        record_stream.close()
        if ref_stream is not None:
            ref_stream.stop_stream()
            ref_stream.close()
        pa.terminate()
        plt.ioff()
        plt.show()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
