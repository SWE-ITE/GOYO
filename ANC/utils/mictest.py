import numpy as np
import pyaudio  # type: ignore
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from collections import deque
import signal

SAMPLE_RATE = 16000
CHUNK = 1024
CHANNELS = 1
WINDOW_SECONDS = 2.0
FORMAT = pyaudio.paInt16

p = pyaudio.PyAudio()
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=SAMPLE_RATE,
    input=True,
    frames_per_buffer=CHUNK,
)

samples_per_window = int(SAMPLE_RATE * WINDOW_SECONDS)
time_axis = np.linspace(-WINDOW_SECONDS, 0, samples_per_window, endpoint=False)
buffer = deque(np.zeros(samples_per_window, dtype=np.float32), maxlen=samples_per_window)

fig, ax = plt.subplots(figsize=(10, 4))
(line,) = ax.plot(time_axis, np.zeros_like(time_axis))
level_text = ax.text(0.02, 0.9, "", transform=ax.transAxes, fontsize=10)

ax.set_xlim(time_axis[0], time_axis[-1] + (WINDOW_SECONDS / samples_per_window))
ax.set_ylim(-1.0, 1.0)
ax.set_xlabel("Time (s)")
ax.set_ylabel("Amplitude")
ax.set_title("Live Microphone Waveform")
ax.grid(True, linestyle="--", linewidth=0.5)

def update(_frame: int):
    raw = stream.read(CHUNK, exception_on_overflow=False)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    buffer.extend(samples)

    waveform = np.asarray(buffer)
    line.set_ydata(waveform)

    rms = np.sqrt(np.mean(waveform**2)) + 1e-12
    level_text.set_text(f"RMS: {20 * np.log10(rms):.1f} dBFS")

    return line, level_text

def cleanup(_event=None):
    if stream.is_active():
        stream.stop_stream()
    stream.close()
    p.terminate()

def handle_sigint(_sig, _frame):
    plt.close(fig)

signal.signal(signal.SIGINT, handle_sigint)
fig.canvas.mpl_connect("close_event", cleanup)

anim = FuncAnimation(fig, update, interval=1000 * CHUNK / SAMPLE_RATE, blit=True)

try:
    plt.show()
finally:
    cleanup()