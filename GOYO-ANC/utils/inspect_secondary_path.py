"""
Inspect the properties of a saved secondary path NumPy array.

Usage:
    python utils/inspect_secondary_path.py [path/to/secondary_path.npy]
"""

import sys
from pathlib import Path
import numpy as np

def main():
    # Default location relative to this script
    default_path = Path(__file__).resolve().parent.parent / "enhanced_ANC" / "secondary_path.npy"
    
    if len(sys.argv) > 1:
        file_path = Path(sys.argv[1])
    else:
        file_path = default_path

    if not file_path.exists():
        print(f"Error: File not found at {file_path}")
        print("Run a measurement script (e.g. enhanced_ANC/lowfreq_cli.py mode=measure) first.")
        return 1

    try:
        h = np.load(file_path)
    except Exception as e:
        print(f"Error loading file: {e}")
        return 1

    print(f"Inspecting: {file_path}")
    print(f"  Shape:       {h.shape}")
    print(f"  Dtype:       {h.dtype}")
    print(f"  Length:      {len(h)}")
    print(f"  Energy:      {np.sum(h**2):.6f}")
    
    peak_idx = np.argmax(np.abs(h))
    print(f"  Peak index:  {peak_idx} (value: {h[peak_idx]:.6f})")

    print("\nFirst 20 taps:")
    print(h[:20])

    return 0

if __name__ == "__main__":
    sys.exit(main())