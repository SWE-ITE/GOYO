"""
List available audio devices using sounddevice.

This script prints the device ID and capabilities (input/output channels, sample rate)
for all audio devices detected by PortAudio. Use the device ID (Index) to configure
the ANC controller.

Run:
    python utils/list_audio_devices.py
"""

from __future__ import annotations

import sounddevice as sd  # type: ignore


def main() -> int:
    try:
        devices = sd.query_devices()
        print(f"Found {len(devices)} device(s):\n")
        print(devices)
        
        # Optionally, print more detailed info if needed
        # for i, dev in enumerate(devices):
        #     print(f"\nDevice {i}: {dev['name']}")
        #     print(f"  Max Input Channels: {dev['max_input_channels']}")
        #     print(f"  Max Output Channels: {dev['max_output_channels']}")
        #     print(f"  Default Sample Rate: {dev['default_samplerate']}")

    except Exception as e:
        print(f"Error listing devices: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
