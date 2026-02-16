"""Tests for audio_analyzer module using synthetic signals."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pytest

from audio_analyzer import (
    calc_energy_ratio,
    calc_peak_dbfs,
    calc_rms_dbfs,
    calc_snr,
    compute_spectrum,
    dominant_freq_band,
    speech_band_energy_ratio,
)

SR = 48000


def _sine_wave(freq: float, duration: float = 1.0, amplitude: float = 0.5) -> np.ndarray:
    """Generate a sine wave."""
    t = np.arange(int(SR * duration)) / SR
    return amplitude * np.sin(2 * np.pi * freq * t)


def _white_noise(duration: float = 1.0, amplitude: float = 0.01) -> np.ndarray:
    rng = np.random.default_rng(42)
    return amplitude * rng.standard_normal(int(SR * duration))


class TestCalcRmsDbfs:
    def test_silence(self):
        signal = np.zeros(SR)
        assert calc_rms_dbfs(signal) == -96.0

    def test_full_scale_sine(self):
        # A sine wave at amplitude 1.0 has RMS = 1/sqrt(2) ≈ 0.707 → -3.01 dBFS
        signal = _sine_wave(1000, amplitude=1.0)
        rms = calc_rms_dbfs(signal)
        assert pytest.approx(rms, abs=0.1) == -3.01

    def test_half_amplitude(self):
        # Amplitude 0.5 → RMS = 0.5/sqrt(2) ≈ 0.354 → -9.03 dBFS
        signal = _sine_wave(1000, amplitude=0.5)
        rms = calc_rms_dbfs(signal)
        assert pytest.approx(rms, abs=0.1) == -9.03

    def test_2d_array(self):
        signal = _sine_wave(1000, amplitude=0.5).reshape(-1, 1)
        rms = calc_rms_dbfs(signal)
        assert pytest.approx(rms, abs=0.1) == -9.03


class TestCalcPeakDbfs:
    def test_silence(self):
        assert calc_peak_dbfs(np.zeros(SR)) == -96.0

    def test_full_scale(self):
        signal = _sine_wave(1000, amplitude=1.0)
        peak = calc_peak_dbfs(signal)
        assert pytest.approx(peak, abs=0.1) == 0.0

    def test_half_amplitude(self):
        signal = _sine_wave(1000, amplitude=0.5)
        peak = calc_peak_dbfs(signal)
        assert pytest.approx(peak, abs=0.1) == -6.02


class TestCalcSnr:
    def test_basic(self):
        assert calc_snr(-10.0, -60.0) == 50.0

    def test_zero(self):
        assert calc_snr(-30.0, -30.0) == 0.0


class TestSpeechBandEnergyRatio:
    def test_speech_frequency(self):
        # 1kHz sine wave should have most energy in the speech band
        signal = _sine_wave(1000, duration=0.5)
        ratio = speech_band_energy_ratio(signal, SR)
        assert ratio > 0.8

    def test_low_frequency(self):
        # 50Hz should have very little energy in speech band
        signal = _sine_wave(50, duration=0.5)
        ratio = speech_band_energy_ratio(signal, SR)
        assert ratio < 0.1

    def test_silence(self):
        assert speech_band_energy_ratio(np.zeros(SR), SR) == 0.0

    def test_empty(self):
        assert speech_band_energy_ratio(np.array([]), SR) == 0.0


class TestComputeSpectrum:
    def test_returns_arrays(self):
        signal = _sine_wave(1000)
        freqs, psd = compute_spectrum(signal, SR)
        assert len(freqs) > 0
        assert len(psd) == len(freqs)

    def test_peak_at_frequency(self):
        signal = _sine_wave(1000, duration=1.0)
        freqs, psd = compute_spectrum(signal, SR)
        peak_freq = freqs[np.argmax(psd)]
        assert abs(peak_freq - 1000) < 50  # Within 50Hz of target


class TestDominantFreqBand:
    def test_silence(self):
        assert dominant_freq_band(np.zeros(SR), SR) == "silence"

    def test_mid_frequency(self):
        signal = _sine_wave(1000)
        band = dominant_freq_band(signal, SR)
        assert "Mid" in band or "500" in band

    def test_bass_frequency(self):
        signal = _sine_wave(100)
        band = dominant_freq_band(signal, SR)
        assert "Bass" in band or "60" in band


class TestCalcEnergyRatio:
    def test_equal_signals(self):
        a = _sine_wave(1000, amplitude=0.5)
        ratio = calc_energy_ratio(a, a)
        assert pytest.approx(ratio, abs=0.01) == 1.0

    def test_louder_a(self):
        a = _sine_wave(1000, amplitude=0.8)
        b = _sine_wave(1000, amplitude=0.4)
        ratio = calc_energy_ratio(a, b)
        assert pytest.approx(ratio, abs=0.01) == 2.0

    def test_silent_b(self):
        a = _sine_wave(1000, amplitude=0.5)
        b = np.zeros(SR)
        assert calc_energy_ratio(a, b) == 0.0
