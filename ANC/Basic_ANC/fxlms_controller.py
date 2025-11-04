"""
FxLMS-based Active Noise Control helper.

This module streams a prerecorded noise track, computes an anti-noise signal
with the filtered-x LMS algorithm, and plays the anti-noise through a speaker
while adapting the control filter using feedback from an error microphone that
is positioned at the listener's ear location.

The implementation favours clarity over raw performance so you can iterate on
the DSP without diving into C extensions. The core loop operates on short
blocks (default: 256 samples) and keeps per-sample state to perform the
filtered-x weight updates.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
import wave
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy as np
import pyaudio  # type: ignore


DEFAULT_SAMPLE_RATE = 16_000
DEFAULT_FILTER_LENGTH = 128
DEFAULT_BLOCK_SIZE = 128
EPSILON = 1e-9  # Small constant to avoid divide-by-zero


@dataclass
class AncMetrics:
    """Lightweight container for streaming diagnostics."""

    frame_index: int
    error_rms: float
    step_size: float


def read_mono_wav(path: str) -> Tuple[np.ndarray, int]:
    """Load a WAV file as a float32 mono array in the range [-1, 1]."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Reference audio not found: {path}")

    with wave.open(path, "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        n_frames = wav_file.getnframes()
        raw = wav_file.readframes(n_frames)

    if sample_width == 2:
        data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sample_width * 8} bits")

    if channels > 1:
        data = data.reshape(-1, channels)[:, 0]

    return data, sample_rate


class FxLMSANC:
    """
    Filtered-x LMS controller for single-channel ANC.

    Parameters
    ----------
    reference_path:
        WAV path for the prerecorded noise reference signal.
    sample_rate:
        Desired operating sample rate. If None, the reference file's rate is used.
    filter_length:
        Number of taps in the adaptive control filter.
    step_size:
        LMS adaptation step. Smaller values converge slower but are safer.
    block_size:
        Number of samples per processing block.
    secondary_path:
        FIR coefficients modelling the speaker→error mic transfer function.
        Provide a 1-D NumPy array. If omitted, an identity path is used.
    control_device_index:
        PyAudio output device index for the anti-noise signal (speaker near user).
    record_device_index:
        Optional PyAudio input device index.
    reference_device_index:
        Optional PyAudio output device index for the primary noise playback.
        Provide this when you need to feed the original noise into a separate
        loudspeaker. If omitted and ``play_reference`` is True, the reference
        signal is mixed into the control speaker instead (legacy behaviour).
    split_reference_channels:
        When True, the control output is stereo with the reference on the left
        channel and the anti-noise on the right channel. Use this to drive both
        signals from a single physical speaker interface.
    play_reference:
        If True, the primary noise is audible. Either written to the dedicated
        reference speaker (when ``reference_device_index`` is set) or mixed into
        the control speaker output.
    normalize_step:
        If True, scales the step size by the energy of the filtered reference
        each sample (NLMS variant of FxLMS).
    """

    def __init__(
        self,
        reference_path: str,
        sample_rate: Optional[int] = None,
        filter_length: int = DEFAULT_FILTER_LENGTH,
        step_size: float = 5e-4,
        block_size: int = DEFAULT_BLOCK_SIZE,
        secondary_path: Optional[np.ndarray] = None,
        control_device_index: Optional[int] = None,
        record_device_index: Optional[int] = None,
        reference_device_index: Optional[int] = None,
        split_reference_channels: bool = False,
        play_reference: bool = False,
        normalize_step: bool = True,
    ):
        self.reference_signal, ref_rate = read_mono_wav(reference_path)

        self.sample_rate = sample_rate or ref_rate
        if self.sample_rate != ref_rate:
            raise ValueError(
                f"Reference sample rate ({ref_rate} Hz) does not match "
                f"requested {self.sample_rate} Hz. Resample the file before use."
            )

        self.filter_length = filter_length
        self.block_size = block_size
        self.base_step_size = step_size
        self.normalize_step = normalize_step
        self.play_reference = play_reference
        self.split_reference_channels = split_reference_channels

        if secondary_path is None:
            # Use a single-sample delta if no model is provided.
            self.secondary_path = np.zeros(8, dtype=np.float32)
            self.secondary_path[0] = 1.0
        else:
            self.secondary_path = np.array(secondary_path, dtype=np.float32)

        if self.secondary_path.ndim != 1:
            raise ValueError("secondary_path must be a 1-D array")

        self.control_device_index = control_device_index
        self.record_device_index = record_device_index
        self.reference_device_index = reference_device_index

        if self.split_reference_channels and self.reference_device_index is not None:
            raise ValueError(
                "Cannot set reference_device_index when split_reference_channels is True."
            )

        self._audio = pyaudio.PyAudio()
        self._control_stream = None
        self._reference_stream = None
        self._input_stream = None
        self._stop_requested = False

        self._reset_state()

    def _reset_state(self) -> None:
        """Initialise adaptive filter state."""
        self.weights = np.zeros(self.filter_length, dtype=np.float32)
        self.ref_history = np.zeros(self.filter_length, dtype=np.float32)
        self.sec_history = np.zeros(len(self.secondary_path), dtype=np.float32)
        self.fx_history = np.zeros(self.filter_length, dtype=np.float32)
        self.reference_index = 0
        self.frame_index = 0

    def stop(self) -> None:
        """Request the processing loop to halt after the current block."""
        self._stop_requested = True

    def _open_streams(self) -> None:
        """Open PyAudio output and input streams."""
        if self._control_stream is None:
            self._control_stream = self._audio.open(
                format=pyaudio.paFloat32,
                channels=2 if self.split_reference_channels else 1,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.block_size,
                output_device_index=self.control_device_index,
            )

        if (
            self.play_reference
            and self.reference_device_index is not None
            and not self.split_reference_channels
            and self._reference_stream is None
        ):
            self._reference_stream = self._audio.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=self.sample_rate,
                output=True,
                frames_per_buffer=self.block_size,
                output_device_index=self.reference_device_index,
            )

        if self._input_stream is None:
            self._input_stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.block_size,
                input_device_index=self.record_device_index,
            )

    def _close_streams(self) -> None:
        """Close streams and terminate PyAudio."""
        if self._control_stream:
            self._control_stream.stop_stream()
            self._control_stream.close()
            self._control_stream = None
        if self._reference_stream:
            self._reference_stream.stop_stream()
            self._reference_stream.close()
            self._reference_stream = None
        if self._input_stream:
            self._input_stream.stop_stream()
            self._input_stream.close()
            self._input_stream = None
        if self._audio:
            self._audio.terminate()

    def _next_reference_block(self, loop: bool) -> np.ndarray:
        """Fetch the next reference block, padding or looping as required."""
        start = self.reference_index
        end = start + self.block_size
        if start >= len(self.reference_signal):
            if loop:
                self.reference_index = 0
                return self._next_reference_block(loop=False)
            return np.zeros(self.block_size, dtype=np.float32)

        block = self.reference_signal[start:end]
        if len(block) < self.block_size:
            if loop:
                remaining = self.block_size - len(block)
                self.reference_index = 0
                block = np.concatenate(
                    [block, self._next_reference_block(loop=False)[:remaining]]
                )
                self.reference_index = remaining
            else:
                block = np.pad(block, (0, self.block_size - len(block)))
                self.reference_index = len(self.reference_signal)
                return block.astype(np.float32)
        else:
            self.reference_index = end
        return block.astype(np.float32)

    def _compute_step(self, fx_vector: np.ndarray) -> float:
        """Adjust step size if normalisation is requested."""
        if not self.normalize_step:
            return self.base_step_size
        energy = float(np.dot(fx_vector, fx_vector)) + EPSILON
        return self.base_step_size / energy

    def run(
        self,
        loop_reference: bool = False,
        max_duration: Optional[float] = None,
        metrics_callback: Optional[Callable[[AncMetrics], None]] = None,
    ) -> None:
        """
        Execute the adaptive control loop.

        Parameters
        ----------
        loop_reference:
            If True, restarts the reference audio when it reaches the end.
        max_duration:
            Optional wall-clock limit in seconds.
        metrics_callback:
            Optional callable invoked once per block with AncMetrics data.
        """
        self._open_streams()
        self._reset_state()
        self._stop_requested = False

        start_time = time.time()

        try:
            while not self._stop_requested:
                if max_duration and (time.time() - start_time) >= max_duration:
                    break

                ref_block = self._next_reference_block(loop_reference)
                if not loop_reference and self.reference_index >= len(
                    self.reference_signal
                ):
                    # We are at the final padded block and will exit next iteration.
                    self._stop_requested = True

                anti_noise_block, fx_vectors = self._synthesize_block(ref_block)

                if self.split_reference_channels:
                    left = ref_block if self.play_reference else np.zeros_like(ref_block)
                    right = anti_noise_block
                    stereo = np.empty(self.block_size * 2, dtype=np.float32)
                    stereo[0::2] = np.clip(left, -1.0, 1.0)
                    stereo[1::2] = np.clip(right, -1.0, 1.0)
                    self._control_stream.write(stereo.tobytes())
                elif self.play_reference and self.reference_device_index is not None and self._reference_stream:
                    self._reference_stream.write(ref_block.astype(np.float32).tobytes())
                    output_block = anti_noise_block
                elif self.play_reference:
                    output_block = np.clip(ref_block + anti_noise_block, -1.0, 1.0)
                else:
                    output_block = np.clip(anti_noise_block, -1.0, 1.0)

                if not self.split_reference_channels:
                    self._control_stream.write(output_block.astype(np.float32).tobytes())

                error_raw = self._input_stream.read(
                    self.block_size, exception_on_overflow=False
                )
                error_block = (
                    np.frombuffer(error_raw, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )

                self._update_weights(error_block, fx_vectors)

                if metrics_callback:
                    error_rms = float(np.sqrt(np.mean(error_block**2)))
                    metrics = AncMetrics(
                        frame_index=self.frame_index,
                        error_rms=error_rms,
                        step_size=self.base_step_size,
                    )
                    metrics_callback(metrics)

                self.frame_index += 1

        except KeyboardInterrupt:
            logging.info("ANC loop interrupted by user.")
        finally:
            self._close_streams()

    def _synthesize_block(
        self, ref_block: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute the anti-noise block and capture filtered-x vectors.

        Returns
        -------
        anti_noise_block:
            Array of length block_size containing the control signal.
        fx_vectors:
            Matrix with shape (block_size, filter_length) containing the
            filtered reference vectors per sample for LMS updates.
        """
        anti_noise = np.zeros(self.block_size, dtype=np.float32)
        fx_vectors = np.zeros((self.block_size, self.filter_length), dtype=np.float32)

        for i in range(self.block_size):
            x_n = ref_block[i]

            # Update reference history
            self.ref_history[1:] = self.ref_history[:-1]
            self.ref_history[0] = x_n

            # Control output y[n] = w^T * x
            anti_noise[i] = float(np.dot(self.weights, self.ref_history))

            # Filtered-x: pass the reference through secondary path estimate
            self.sec_history[1:] = self.sec_history[:-1]
            self.sec_history[0] = x_n
            filtered_sample = float(np.dot(self.secondary_path, self.sec_history))

            self.fx_history[1:] = self.fx_history[:-1]
            self.fx_history[0] = filtered_sample

            fx_vectors[i] = self.fx_history

        return anti_noise, fx_vectors

    def _update_weights(self, error_block: np.ndarray, fx_vectors: np.ndarray) -> None:
        """LMS weight adaptation for the current block."""
        for e, fx in zip(error_block, fx_vectors):
            step = self._compute_step(fx)
            self.weights += step * e * fx

    def measure_secondary_path(
        self,
        duration: float = 2.0,
        excitation_level: float = 0.2,
        fir_length: int = 64,
    ) -> np.ndarray:
        """
        Excite the secondary path (speaker→mic) and estimate an FIR model.

        This sends white noise to the speaker for the requested duration,
        records the response at the error microphone, and solves a least-squares
        problem to approximate the impulse response.
        """
        self._open_streams()

        n_samples = int(duration * self.sample_rate)
        excitation = np.random.uniform(-1.0, 1.0, size=n_samples).astype(np.float32)
        excitation *= excitation_level

        recorded = np.zeros(n_samples, dtype=np.float32)
        ptr = 0

        logging.info("Measuring secondary path for %.2f s", duration)

        while ptr < n_samples:
            block = excitation[ptr : ptr + self.block_size]
            if len(block) < self.block_size:
                block = np.pad(block, (0, self.block_size - len(block)))

            if self.split_reference_channels:
                stereo_block = np.zeros(self.block_size * 2, dtype=np.float32)
                stereo_block[1::2] = block.astype(np.float32)
                self._control_stream.write(stereo_block.tobytes())
            else:
                self._control_stream.write(block.astype(np.float32).tobytes())
            raw = self._input_stream.read(
                self.block_size, exception_on_overflow=False
            )
            error_block = (
                np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            )
            slice_len = min(self.block_size, n_samples - ptr)
            recorded[ptr : ptr + slice_len] = error_block[:slice_len]
            ptr += self.block_size

        # Build Toeplitz matrix for least squares: y = Xh
        X = np.zeros((n_samples - fir_length, fir_length), dtype=np.float32)
        for i in range(fir_length):
            X[:, i] = excitation[i : i + n_samples - fir_length]
        y = recorded[fir_length:]

        h, *_ = np.linalg.lstsq(X, y, rcond=None)
        self.secondary_path = h.astype(np.float32)
        logging.info("Secondary path updated (length %d)", fir_length)
        return self.secondary_path.copy()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run FxLMS ANC session.")
    parser.add_argument("reference_path", help="Path to reference noise WAV file")
    parser.add_argument(
        "--filter-length",
        type=int,
        default=DEFAULT_FILTER_LENGTH,
        help="Number of taps in the adaptive filter",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=DEFAULT_BLOCK_SIZE,
        help="Processing block size in samples",
    )
    parser.add_argument(
        "--step-size",
        type=float,
        default=5e-4,
        help="Base LMS step size",
    )
    parser.add_argument(
        "--play-reference",
        action="store_true",
        help="Audibly play the reference noise (requires --reference-device for separate speaker)",
    )
    parser.add_argument(
        "--control-device",
        type=int,
        default=None,
        help="Output device index for anti-noise speaker",
    )
    parser.add_argument(
        "--reference-device",
        type=int,
        default=None,
        help="Output device index for reference noise speaker",
    )
    parser.add_argument(
        "--record-device",
        type=int,
        default=None,
        help="Input device index for error microphone",
    )
    parser.add_argument(
        "--split-reference-channels",
        action="store_true",
        help="Send reference (left) and anti-noise (right) over the control output stereo pair",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional maximum runtime in seconds",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    controller = FxLMSANC(
        reference_path=args.reference_path,
        filter_length=args.filter_length,
        block_size=args.block_size,
        step_size=args.step_size,
        play_reference=args.play_reference,
        control_device_index=args.control_device,
        record_device_index=args.record_device,
        reference_device_index=args.reference_device,
        split_reference_channels=args.split_reference_channels,
    )

    def log_metrics(metrics: AncMetrics) -> None:
        logging.info(
            "frame=%05d error_rms=%.6f",
            metrics.frame_index,
            metrics.error_rms,
        )

    controller.run(
        loop_reference=True if args.duration else False,
        max_duration=args.duration,
        metrics_callback=log_metrics,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
