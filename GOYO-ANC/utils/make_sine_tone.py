"""
Generate a sine wave WAV file for ANC testing.

Usage:
    python utils/make_sine_tone.py [output_filename] [options]

Example:
    python utils/make_sine_tone.py sine_200Hz.wav --freq 200 --duration 60
"""

import argparse
import sys
import numpy as np
import soundfile as sf
from pathlib import Path

def generate_sine_wave(
    filename: str,
    freq: float,
    duration: float,
    amplitude: float,
    fs: int
) -> None:
    """Generate and save a mono sine wave."""
    print(f"Generating {duration}s sine wave at {freq}Hz (amp={amplitude}, fs={fs})...")
    
    # Time array
    t = np.linspace(0, duration, int(fs * duration), endpoint=False)
    
    # Signal generation
    signal = amplitude * np.sin(2 * np.pi * freq * t)
    
    # Ensure directory exists if path includes directories
    output_path = Path(filename)
    if output_path.parent.name:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
    # Write to file
    sf.write(output_path, signal, fs)
    print(f"Successfully saved to '{output_path}'.")


def main():
    parser = argparse.ArgumentParser(description="Generate a sine tone WAV file.")
    parser.add_argument(
        "filename", 
        nargs="?", 
        default="sine_200Hz_200s.wav",
        help="Output WAV filename (default: sine_200Hz_200s.wav)"
    )
    parser.add_argument(
        "--freq", 
        type=float, 
        default=200.0, 
        help="Frequency in Hz (default: 200.0)"
    )
    parser.add_argument(
        "--duration", 
        type=float, 
        default=200.0, 
        help="Duration in seconds (default: 200.0)"
    )
    parser.add_argument(
        "--amp", 
        type=float, 
        default=0.3, 
        help="Amplitude 0.0-1.0 (default: 0.3)"
    )
    parser.add_argument(
        "--fs", 
        type=int, 
        default=48000, 
        help="Sample rate in Hz (default: 48000)"
    )

    args = parser.parse_args()

    generate_sine_wave(
        args.filename,
        args.freq,
        args.duration,
        args.amp,
        args.fs
    )

if __name__ == "__main__":
    main()