"""Tests for speaker_playback module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import tempfile

import numpy as np
import pytest
import soundfile as sf

from speaker_playback import (
    find_meeting_files,
    generate_synthetic_music,
)


class TestFindMeetingFiles:
    def test_nonexistent_directory(self):
        files = find_meeting_files("/nonexistent/path/that/does/not/exist")
        assert files == []

    def test_empty_directory(self, tmp_path):
        files = find_meeting_files(str(tmp_path))
        assert files == []

    def test_finds_opus_files(self, tmp_path):
        # Create fake opus files
        for i in range(3):
            f = tmp_path / f"meeting_{i}.opus"
            # Write >5MB of data
            f.write_bytes(b"\x00" * 6_000_000)

        files = find_meeting_files(str(tmp_path))
        assert len(files) == 3

    def test_filters_small_files(self, tmp_path):
        big = tmp_path / "big.opus"
        big.write_bytes(b"\x00" * 6_000_000)
        small = tmp_path / "small.opus"
        small.write_bytes(b"\x00" * 1_000)

        files = find_meeting_files(str(tmp_path))
        assert len(files) == 1

    def test_limit(self, tmp_path):
        for i in range(5):
            f = tmp_path / f"meeting_{i}.opus"
            f.write_bytes(b"\x00" * 6_000_000)

        files = find_meeting_files(str(tmp_path), limit=2)
        assert len(files) == 2

    def test_recursive_discovery(self, tmp_path):
        subdir = tmp_path / "2024" / "01"
        subdir.mkdir(parents=True)
        f = subdir / "meeting.opus"
        f.write_bytes(b"\x00" * 6_000_000)

        files = find_meeting_files(str(tmp_path))
        assert len(files) == 1


class TestGenerateSyntheticMusic:
    def test_generates_wav(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name

        try:
            result = generate_synthetic_music(output_path=path, duration=4.0)
            assert os.path.exists(result)

            # Read and verify
            data, sr = sf.read(result)
            assert sr == 44100
            assert len(data) > 0
            # ~4 seconds at 44100 Hz
            assert abs(len(data) - 4 * 44100) < 100
        finally:
            os.unlink(path)

    def test_not_silent(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name

        try:
            result = generate_synthetic_music(output_path=path, duration=2.0)
            data, sr = sf.read(result)
            rms = np.sqrt(np.mean(data ** 2))
            assert rms > 0.01  # Not silent
        finally:
            os.unlink(path)

    def test_no_clipping(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            path = f.name

        try:
            result = generate_synthetic_music(output_path=path, duration=4.0)
            data, sr = sf.read(result)
            assert np.max(np.abs(data)) <= 1.0
        finally:
            os.unlink(path)
