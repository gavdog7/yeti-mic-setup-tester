from __future__ import annotations

"""Audio analysis functions for Blue Yeti calibration.

Provides RMS, peak, SNR, spectral analysis, and frequency band identification.
All level measurements are in dBFS (decibels relative to full scale).
"""

import numpy as np
from scipy.signal import welch


def calc_rms_dbfs(signal: np.ndarray) -> float:
    """Calculate RMS level in dBFS.

    Args:
        signal: Audio signal as float64 array, normalized to [-1.0, 1.0].

    Returns:
        RMS level in dBFS. Returns -96.0 for silence.
    """
    signal = signal.astype(np.float64).flatten()
    rms = np.sqrt(np.mean(signal ** 2))
    if rms > 0:
        return 20.0 * np.log10(rms)
    return -96.0


def calc_peak_dbfs(signal: np.ndarray) -> float:
    """Calculate peak level in dBFS.

    Args:
        signal: Audio signal as float64 array, normalized to [-1.0, 1.0].

    Returns:
        Peak level in dBFS. Returns -96.0 for silence.
    """
    signal = signal.astype(np.float64).flatten()
    peak = np.max(np.abs(signal))
    if peak > 0:
        return 20.0 * np.log10(peak)
    return -96.0


def calc_snr(signal_rms_dbfs: float, noise_floor_dbfs: float) -> float:
    """Calculate signal-to-noise ratio in dB.

    Args:
        signal_rms_dbfs: Signal RMS level in dBFS.
        noise_floor_dbfs: Noise floor RMS level in dBFS.

    Returns:
        SNR in dB.
    """
    return signal_rms_dbfs - noise_floor_dbfs


def speech_band_energy_ratio(signal: np.ndarray, sr: int) -> float:
    """Calculate the ratio of energy in the speech band (300Hz-3kHz) to total energy.

    Args:
        signal: Audio signal array.
        sr: Sample rate in Hz.

    Returns:
        Ratio of speech band energy to total energy (0.0 to 1.0).
    """
    signal = signal.astype(np.float64).flatten()
    if len(signal) == 0 or np.all(signal == 0):
        return 0.0

    nperseg = min(4096, len(signal))
    freqs, psd = welch(signal, fs=sr, nperseg=nperseg)
    total_energy = np.sum(psd)
    if total_energy == 0:
        return 0.0

    speech_mask = (freqs >= 300) & (freqs <= 3000)
    speech_energy = np.sum(psd[speech_mask])
    return float(speech_energy / total_energy)


def compute_spectrum(signal: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    """Compute power spectral density using Welch's method.

    Args:
        signal: Audio signal array.
        sr: Sample rate in Hz.

    Returns:
        Tuple of (frequencies, power_spectral_density) arrays.
    """
    signal = signal.astype(np.float64).flatten()
    nperseg = min(4096, len(signal)) if len(signal) > 0 else 256
    freqs, psd = welch(signal, fs=sr, nperseg=nperseg)
    return freqs, psd


def dominant_freq_band(signal: np.ndarray, sr: int) -> str:
    """Identify the dominant frequency band in the signal.

    Bands:
        Sub-bass: 20-60 Hz
        Bass: 60-250 Hz
        Low-mid: 250-500 Hz
        Mid: 500-2000 Hz
        Upper-mid: 2000-4000 Hz
        Presence: 4000-6000 Hz
        Brilliance: 6000-20000 Hz

    Args:
        signal: Audio signal array.
        sr: Sample rate in Hz.

    Returns:
        Name of the dominant frequency band.
    """
    signal = signal.astype(np.float64).flatten()
    if len(signal) == 0 or np.all(signal == 0):
        return "silence"

    freqs, psd = compute_spectrum(signal, sr)

    bands = [
        ("Sub-bass (20-60 Hz)", 20, 60),
        ("Bass (60-250 Hz)", 60, 250),
        ("Low-mid (250-500 Hz)", 250, 500),
        ("Mid (500-2kHz)", 500, 2000),
        ("Upper-mid (2-4 kHz)", 2000, 4000),
        ("Presence (4-6 kHz)", 4000, 6000),
        ("Brilliance (6-20 kHz)", 6000, 20000),
    ]

    max_energy = 0.0
    dominant = "unknown"
    for name, low, high in bands:
        mask = (freqs >= low) & (freqs < high)
        energy = np.sum(psd[mask])
        if energy > max_energy:
            max_energy = energy
            dominant = name

    return dominant


def calc_energy_ratio(signal_a: np.ndarray, signal_b: np.ndarray) -> float:
    """Calculate the RMS energy ratio between two signals.

    Args:
        signal_a: First signal (e.g., voice recording).
        signal_b: Second signal (e.g., TV-only recording).

    Returns:
        Ratio of signal_a RMS to signal_b RMS. Returns 0.0 if signal_b is silent.
    """
    rms_a = np.sqrt(np.mean(signal_a.astype(np.float64).flatten() ** 2))
    rms_b = np.sqrt(np.mean(signal_b.astype(np.float64).flatten() ** 2))
    if rms_b == 0:
        return 0.0
    return float(rms_a / rms_b)
