import numpy as np
from scipy.signal import periodogram


def calculate_alpha_amplitude(
    data_segment: np.ndarray,
    fs: float,
    alpha_low: float,
    alpha_high: float,
    window_size: int,
) -> float:
    if len(data_segment) < window_size:
        return 0.0

    x = np.asarray(data_segment, dtype=float)
    x = x - np.mean(x)

    freqs, psd = periodogram(
        x,
        fs=fs,
        window="hann",
        detrend=False,
        scaling="density",
    )

    band = (freqs >= alpha_low) & (freqs <= alpha_high)
    if not np.any(band):
        return 0.0

    alpha_power = np.trapezoid(psd[band], freqs[band])
    return float(np.sqrt(alpha_power))


def calculate_emg_amplitude(data_segment: np.ndarray) -> float:
    if len(data_segment) == 0:
        return 0.0
    try:
        return float(np.sqrt(np.mean(np.asarray(data_segment, dtype=float) ** 2)))
    except Exception:
        return 0.0
