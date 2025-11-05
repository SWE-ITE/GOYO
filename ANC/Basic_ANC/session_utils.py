"""
Shared helpers for ANC scripts in ``Basic_ANC``.

These utilities centralise common tasks such as loading the secondary-path
estimate, constructing the FxLMS controller, and streaming the reference
signal through PyAudio. The goal is to keep the runnable entrypoints small
and focused on orchestration rather than boilerplate.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import numpy as np
import pyaudio  # type: ignore

from fxlms_controller import DEFAULT_BLOCK_SIZE, FxLMSANC, read_mono_wav


def load_secondary_path(path: Path) -> np.ndarray:
    """Load a saved secondary-path impulse response."""
    if not path.exists():
        raise FileNotFoundError(f"Secondary path file not found: {path}")
    taps = np.load(path)
    if taps.ndim != 1:
        raise ValueError("Secondary path taps must be a 1-D array")
    return taps.astype(np.float32)


def create_controller(
    reference_path: Path,
    *,
    secondary_path_file: Optional[Path] = None,
    control_device: Optional[int] = None,
    record_device: Optional[int] = None,
    reference_device: Optional[int] = None,
    split_reference_channels: bool = False,
    play_reference: bool = False,
    step_size: float = 5e-4,
    block_size: Optional[int] = None,
    filter_length: Optional[int] = None,
) -> FxLMSANC:
    """
    Construct an ``FxLMSANC`` instance with shared configuration defaults.
    """
    init_kwargs = {
        "reference_path": str(reference_path),
        "control_device_index": control_device,
        "record_device_index": record_device,
        "reference_device_index": reference_device,
        "split_reference_channels": split_reference_channels,
        "play_reference": play_reference,
        "step_size": step_size,
    }
    if secondary_path_file is not None:
        init_kwargs["secondary_path"] = load_secondary_path(secondary_path_file)
    if block_size is not None:
        init_kwargs["block_size"] = block_size
    if filter_length is not None:
        init_kwargs["filter_length"] = filter_length

    return FxLMSANC(**init_kwargs)


def play_reference(
    reference_path: Path,
    *,
    control_device: Optional[int],
    reference_device: Optional[int],
    split_reference_channels: bool,
    block_size: Optional[int],
    duration: Optional[float],
    loop: bool,
) -> None:
    """
    Stream the reference signal to the specified output(s).

    Args:
        reference_path: Audio file to play.
        control_device: PyAudio output device for the control speaker.
        reference_device: Optional dedicated device for the reference speaker.
        split_reference_channels: When True, send reference/anti-noise over one stereo device.
        block_size: Samples per audio callback; defaults to ``DEFAULT_BLOCK_SIZE``.
        duration: Optional wall-clock limit in seconds.
        loop: When True, restart playback after reaching the end.
    """
    signal, sample_rate = read_mono_wav(str(reference_path))
    block_len = block_size if block_size is not None else DEFAULT_BLOCK_SIZE

    pa = pyaudio.PyAudio()
    control_stream = pa.open(
        format=pyaudio.paFloat32,
        channels=2 if split_reference_channels else 1,
        rate=sample_rate,
        output=True,
        frames_per_buffer=block_len,
        output_device_index=control_device,
    )
    reference_stream = None
    if reference_device is not None:
        reference_stream = pa.open(
            format=pyaudio.paFloat32,
            channels=1,
            rate=sample_rate,
            output=True,
            frames_per_buffer=block_len,
            output_device_index=reference_device,
        )

    index = 0
    start_time = time.time()
    try:
        while True:
            if duration is not None and (time.time() - start_time) >= duration:
                break

            block = signal[index : index + block_len]
            if len(block) == 0:
                if loop:
                    index = 0
                    continue
                break

            if len(block) < block_len:
                block = np.pad(block, (0, block_len - len(block))).astype(np.float32)
            else:
                block = np.array(block, dtype=np.float32, copy=False)

            if split_reference_channels:
                stereo = np.zeros(block_len * 2, dtype=np.float32)
                stereo[0::2] = block
                control_stream.write(stereo.tobytes())
            else:
                control_stream.write(block.tobytes())

            if reference_stream is not None:
                reference_stream.write(block.tobytes())

            index += block_len
            if index >= len(signal):
                if loop:
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
