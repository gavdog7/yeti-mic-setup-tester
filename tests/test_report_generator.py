"""Tests for report_generator module — recommendations and success criteria."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import tempfile

import numpy as np
import pytest

from report_generator import (
    check_success_criteria,
    generate_comparison_table,
    generate_measurements_table,
    generate_recommendations,
    generate_report_markdown,
    recommend_pattern,
    recommend_positioning,
    save_final_config,
    save_results_json,
)


def _make_results(
    p1_rms=-60.0,
    p2_rms=-20.0, p2_peak=-6.0, p2_snr=40.0,
    p3_rms=-35.0, p3_snr=25.0,
    p4_rms=-18.0, p4_dominance=3.0,
    p5_rms=-17.0, p5_music_ratio=0.15,
) -> dict:
    """Create a mock results dict for testing."""
    return {
        "phase1": {
            "rms_dbfs": p1_rms,
            "peak_dbfs": p1_rms + 10,
            "dominant_band": "Bass (60-250 Hz)",
            "spectrum": {"freqs": np.array([0, 100, 1000]), "psd": np.array([0.1, 0.2, 0.1])},
        },
        "phase2": {
            "rms_dbfs": p2_rms,
            "peak_dbfs": p2_peak,
            "snr_db": p2_snr,
            "dominant_band": "Mid (500-2kHz)",
            "speech_band_ratio": 0.7,
            "spectrum": {"freqs": np.array([0, 100, 1000]), "psd": np.array([0.1, 0.5, 0.8])},
        },
        "phase3": {
            "rms_dbfs": p3_rms,
            "peak_dbfs": p3_rms + 10,
            "snr_db": p3_snr,
            "dominant_band": "Mid (500-2kHz)",
            "spectrum": {"freqs": np.array([0, 100, 1000]), "psd": np.array([0.1, 0.3, 0.4])},
        },
        "phase4": {
            "rms_dbfs": p4_rms,
            "peak_dbfs": p4_rms + 5,
            "snr_db": 42.0,
            "voice_dominance_ratio": p4_dominance,
            "dominant_band": "Mid (500-2kHz)",
            "spectrum": {"freqs": np.array([0, 100, 1000]), "psd": np.array([0.1, 0.5, 0.9])},
        },
        "phase5": {
            "rms_dbfs": p5_rms,
            "peak_dbfs": p5_rms + 5,
            "snr_db": 43.0,
            "music_energy_ratio": p5_music_ratio,
            "dominant_band": "Mid (500-2kHz)",
            "spectrum": {"freqs": np.array([0, 100, 1000]), "psd": np.array([0.1, 0.5, 1.0])},
        },
    }


class TestGenerateRecommendations:
    def test_good_results(self):
        results = _make_results()
        recs = generate_recommendations(results)
        severities = [r["severity"] for r in recs]
        # All good results should be passes/info
        assert "danger" not in severities
        assert "warning" not in severities

    def test_high_noise_floor(self):
        results = _make_results(p1_rms=-45.0)
        recs = generate_recommendations(results)
        noise_recs = [r for r in recs if "Noise floor" in r["condition"] or "noise" in r["condition"].lower()]
        assert any(r["severity"] == "warning" for r in noise_recs)

    def test_clipping_risk(self):
        results = _make_results(p2_peak=-1.0)
        recs = generate_recommendations(results)
        clip_recs = [r for r in recs if "Clipping" in r["condition"] or "clip" in r["condition"].lower()]
        assert any(r["severity"] == "danger" for r in clip_recs)

    def test_voice_too_quiet(self):
        results = _make_results(p2_snr=10.0)
        recs = generate_recommendations(results)
        voice_recs = [r for r in recs if "Voice" in r["condition"] or "voice" in r["condition"].lower()]
        assert any(r["severity"] == "warning" for r in voice_recs)

    def test_tv_barely_audible(self):
        results = _make_results(p3_snr=3.0)
        recs = generate_recommendations(results)
        tv_recs = [r for r in recs if "TV" in r["condition"] or "tv" in r["condition"].lower()]
        assert any(r["severity"] == "warning" for r in tv_recs)

    def test_voice_not_dominant(self):
        results = _make_results(p4_dominance=1.2)
        recs = generate_recommendations(results)
        dom_recs = [r for r in recs if "dominant" in r["condition"].lower() or "dominance" in r["condition"].lower()]
        assert any(r["severity"] == "warning" for r in dom_recs)

    def test_music_too_prominent(self):
        results = _make_results(p5_music_ratio=0.4)
        recs = generate_recommendations(results)
        music_recs = [r for r in recs if "Music" in r["condition"] or "music" in r["condition"].lower()]
        assert any(r["severity"] == "warning" for r in music_recs)


class TestRecommendPattern:
    def test_default_cardioid(self):
        results = _make_results()
        pattern = recommend_pattern(results)
        assert pattern["pattern"] == "Cardioid"

    def test_low_tv_snr_suggests_omni(self):
        results = _make_results(p3_snr=3.0)
        pattern = recommend_pattern(results)
        assert pattern["pattern"] == "Omnidirectional"

    def test_high_dominance_suggests_omni(self):
        results = _make_results(p4_dominance=12.0)
        pattern = recommend_pattern(results)
        assert pattern["pattern"] == "Omnidirectional"


class TestCheckSuccessCriteria:
    def test_all_pass(self):
        results = _make_results()
        criteria = check_success_criteria(results)
        assert all(c["passed"] for c in criteria)

    def test_noise_floor_fail(self):
        results = _make_results(p1_rms=-50.0)
        criteria = check_success_criteria(results)
        noise = [c for c in criteria if c["name"] == "Noise floor"][0]
        assert not noise["passed"]

    def test_voice_snr_fail(self):
        results = _make_results(p2_snr=15.0)
        criteria = check_success_criteria(results)
        voice = [c for c in criteria if c["name"] == "Voice SNR"][0]
        assert not voice["passed"]

    def test_clipping_fail(self):
        results = _make_results(p2_peak=-2.0)
        criteria = check_success_criteria(results)
        clip = [c for c in criteria if c["name"] == "No clipping"][0]
        assert not clip["passed"]


class TestGenerateReportMarkdown:
    def test_generates_markdown(self):
        results = _make_results()
        md = generate_report_markdown(results, 1)
        assert "# Blue Yeti Calibration Report" in md
        assert "Run 001" in md
        assert "Recommendations" in md
        assert "Success Criteria" in md

    def test_with_previous_results(self):
        results = _make_results()
        prev = _make_results(p2_snr=30.0)
        md = generate_report_markdown(results, 2, prev)
        assert "Comparison" in md


class TestSaveResultsJson:
    def test_creates_file(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        os.unlink(path)  # Start fresh

        try:
            results = _make_results()
            save_results_json(results, 1, json_path=path)
            assert os.path.exists(path)

            with open(path) as f:
                data = json.load(f)
            assert len(data["runs"]) == 1
            assert data["runs"][0]["run_number"] == 1
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_appends_to_existing(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        os.unlink(path)

        try:
            results = _make_results()
            save_results_json(results, 1, json_path=path)
            save_results_json(results, 2, json_path=path)

            with open(path) as f:
                data = json.load(f)
            assert len(data["runs"]) == 2
        finally:
            if os.path.exists(path):
                os.unlink(path)


class TestSaveFinalConfig:
    def test_creates_config(self):
        results = _make_results()
        path = save_final_config(results, device_index=3)
        assert os.path.exists(path)

        with open(path) as f:
            config = json.load(f)
        assert config["preferred_input_device"] == "Blue Yeti"
        assert config["device_index"] == 3
        assert config["sample_rate"] == 48000
        assert config["channels"] == 1
        assert "calibrated_at" in config
