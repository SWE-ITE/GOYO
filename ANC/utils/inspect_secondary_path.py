import numpy as np

h = np.load("ANC/enhanced_ANC/secondary_path.npy")

print("length:", len(h))
print("first 20 taps:\n", h[:20])
print("peak index:", np.argmax(np.abs(h)))
print("energy:", np.sum(h**2))