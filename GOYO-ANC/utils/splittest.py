"""
Quick stereo sanity check: plays different tones on left and right channels.

Run from the repo root:
    python -m ANC.splittest --device 1
"""

from __future__ import annotations

import argparse
import math
import time

import numpy as np
import pyaudio  # type: ignore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stereo split speaker test.")
    parser.add_argument(
        "--device",
        type=int,
        default=3,
        help="PyAudio output device index for the stereo speaker (default: 1)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Playback duration in seconds (default: 5)",
    )
    parser.add_argument(
        "--sample-rate",
        type=int,
        default=48_000,
        help="Sample rate in Hz (default: 48000)",
    )
    parser.add_argument(
        "--left-freq",
        type=float,
        default=440.0,
        help="Left-channel test tone frequency in Hz (default: 440)",
    )
    parser.add_argument(
        "--right-freq",
        type=float,
        default=660.0,
        help="Right-channel test tone frequency in Hz (default: 660)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    pa = pyaudio.PyAudio()
    info = pa.get_device_info_by_index(args.device)
    if info.get("maxOutputChannels", 0) < 2:
        raise RuntimeError(f"Device {args.device} does not support stereo output.")

    stream = pa.open(
        format=pyaudio.paFloat32,
        channels=2,
        rate=args.sample_rate,
        frames_per_buffer=1024,
        output=True,
        output_device_index=args.device,
    )

    total_frames = int(args.duration * args.sample_rate)
    t = np.arange(total_frames, dtype=np.float32) / args.sample_rate

    left = 0.4 * np.sin(2 * math.pi * args.left_freq * t)
    right = 0.4 * np.sin(2 * math.pi * args.right_freq * t)

    interleaved = np.empty(total_frames * 2, dtype=np.float32)
    interleaved[0::2] = left
    interleaved[1::2] = right

    stream.write(interleaved.tobytes())
    time.sleep(args.duration)

    stream.stop_stream()
    stream.close()
    pa.terminate()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
