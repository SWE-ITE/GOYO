from __future__ import annotations

"""
Quick smoke test for the AI-enhanced ANC controller.

Run via: `python -m ANC.AI_ANC.run_ai_anc_demo`
"""

import numpy as np

from .controller import AIANCController


def generate_synthetic_secondary_path(num_samples: int, delay: int = 4) -> tuple[np.ndarray, np.ndarray]:
    # Signal for testing: white noise
    excitation = np.random.randn(num_samples).astype(np.float32)
    # Simple secondary path: impulse response with a delay and two taps
    impulse = np.zeros(delay + 1, dtype=np.float32)
    impulse[delay] = 0.6
    impulse[0] = 0.3
    response = np.convolve(excitation, impulse, mode="same")
    return excitation, response


def main() -> None:
    np.random.seed(0)
    controller = AIANCController(filter_length=64)

    # Train the secondary path model with synthetic data
    excitation, response = generate_synthetic_secondary_path(4096)
    history = controller.train_secondary_path(excitation, response, epochs=5, batch_size=128)
    print("Secondary path training loss history:", history)
    
    # Train the reference signal predictor
    reference_signal = np.sin(2 * np.pi * 0.01 * np.arange(8192)).astype(np.float32)
    predictor_loss = controller.fit_reference_predictor(reference_signal, epochs=5)
    print("Predictor loss:", predictor_loss)

    # Validate the controller processing on a test block
    reference_block = np.sin(2 * np.pi * 0.02 * np.arange(256)).astype(np.float32)
    error_block = 0.5 * np.random.randn(256).astype(np.float32)

    metrics = controller.process_block(reference_block, error_block)
    print("Controller metrics:", metrics)


if __name__ == "__main__":
    main()
