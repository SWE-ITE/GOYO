"""
List available audio devices with PyAudio.

Run:
    python utils/list_audio_devices.py
"""

from __future__ import annotations

import pyaudio  # type: ignore


def main() -> int:
    pa = pyaudio.PyAudio()
    try:
        count = pa.get_device_count()
        print(f"device_count={count}")
        for i in range(count):
            info = pa.get_device_info_by_index(i)
            print(
                f"[{i}] {info['name']}  "
                f"inputs={info['maxInputChannels']}  "
                f"outputs={info['maxOutputChannels']}  "
                f"rate={int(info['defaultSampleRate'])}"
            )
    finally:
        pa.terminate()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
