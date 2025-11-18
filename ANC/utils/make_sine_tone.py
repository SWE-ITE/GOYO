import numpy as np
import soundfile as sf

# ---------------------------------------
# Configuration
# ---------------------------------------
fs = 16000          # Sample rate in Hz
duration = 200.0     # Duration in seconds
freq = 200.0        # Frequency of the sine wave in Hz
amplitude = 0.3     # Amplitude (0–1 range)

# ---------------------------------------
# Generate sine wave
# ---------------------------------------
t = np.linspace(0, duration, int(fs * duration), endpoint=False)
signal = amplitude * np.sin(2 * np.pi * freq * t)

# ---------------------------------------
# Save to WAV file
# ---------------------------------------
sf.write("sine_200Hz200s.wav", signal, fs)
print(" 'sine_200Hz.wav' has been created successfully.")