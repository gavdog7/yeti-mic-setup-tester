from __future__ import annotations

"""Speaker playback and meeting file discovery for Blue Yeti calibration.

Handles finding meeting recordings, converting opus to WAV, playing audio
through system speakers via afplay, and generating synthetic music.
"""

import glob
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

GRANULARSYNC_DIR = "/Volumes/4TBSSD/granularSync"
MIN_FILE_SIZE = 5_000_000  # 5 MB

# Pre-selected meeting file with confirmed speech content.
# Jason meeting (2026-02-15, 37min) — 85.7% speech band energy, good volume.
# Extract from 2:00 offset to skip intro silence and get into conversation.
PREFERRED_MEETING_FILE = (
    "/Volumes/4TBSSD/granularSync/2026-02-15/"
    "2026-02-15__00__1722__Jason__Notes/"
    "2026-02-15__02__2322__Jason__jason.rardin@gmail.com__37min.opus"
)
PREFERRED_MEETING_OFFSET_SECS = 120  # Skip first 2 minutes


def find_meeting_files(directory: str = GRANULARSYNC_DIR, limit: int = 10) -> list[str]:
    """Discover .opus meeting files, filtered by size and sorted by recency.

    Args:
        directory: Root directory to search.
        limit: Maximum number of files to return.

    Returns:
        List of file paths sorted by modification time (newest first).
    """
    if not os.path.isdir(directory):
        return []

    opus_files = glob.glob(os.path.join(directory, "**", "*.opus"), recursive=True)
    opus_files = [f for f in opus_files if os.path.getsize(f) > MIN_FILE_SIZE]
    opus_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
    return opus_files[:limit]


def find_meeting_file(directory: str = GRANULARSYNC_DIR) -> str | None:
    """Find the most recent meeting file.

    Returns:
        Path to the most recent .opus file, or None if none found.
    """
    files = find_meeting_files(directory)
    return files[0] if files else None


def check_ffmpeg() -> bool:
    """Check if ffmpeg is available."""
    return shutil.which("ffmpeg") is not None


def convert_to_wav(
    opus_path: str,
    output_path: str | None = None,
    offset_secs: int | None = None,
    duration_secs: int | None = None,
) -> str:
    """Convert an audio file to WAV using ffmpeg, optionally extracting a segment.

    Args:
        opus_path: Path to the input audio file.
        output_path: Optional output path. Defaults to /tmp/calibration_meeting.wav.
        offset_secs: Start time in seconds (skip this many seconds from the start).
        duration_secs: Duration in seconds to extract. None = rest of file.

    Returns:
        Path to the converted WAV file.

    Raises:
        FileNotFoundError: If ffmpeg is not installed.
        RuntimeError: If conversion fails.
    """
    if not check_ffmpeg():
        raise FileNotFoundError(
            "ffmpeg not found. Install it with: brew install ffmpeg"
        )

    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), "calibration_meeting.wav")

    cmd = ["ffmpeg", "-y"]
    if offset_secs is not None:
        cmd.extend(["-ss", str(offset_secs)])
    cmd.extend(["-i", opus_path])
    if duration_secs is not None:
        cmd.extend(["-t", str(duration_secs)])
    cmd.extend(["-ar", "44100", "-ac", "1", output_path])

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {result.stderr[:500]}")

    return output_path


def prepare_calibration_meeting_clip() -> str | None:
    """Prepare the pre-selected meeting clip for calibration playback.

    Uses the preferred meeting file (known to contain clear speech) and
    extracts from the speech-heavy section. Falls back to auto-discovery
    if the preferred file is unavailable.

    Returns:
        Path to the ready-to-play WAV file, or None if unavailable.
    """
    if not check_ffmpeg():
        return None

    # Try the pre-selected file first
    source = PREFERRED_MEETING_FILE
    offset = PREFERRED_MEETING_OFFSET_SECS

    if not os.path.isfile(source):
        # Fallback to auto-discovery
        source = find_meeting_file()
        offset = 120  # Still skip the first 2 minutes
        if source is None:
            return None

    try:
        return convert_to_wav(source, offset_secs=offset)
    except RuntimeError:
        return None


def play_audio(wav_path: str, volume: float = 1.0) -> subprocess.Popen:
    """Play a WAV file through system speakers via afplay.

    Args:
        wav_path: Path to the WAV file.
        volume: Volume level (0.0 to 1.0).

    Returns:
        Popen process handle for the playback.
    """
    cmd = ["afplay", "--volume", str(volume), wav_path]
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def stop_audio(process: subprocess.Popen) -> None:
    """Stop an audio playback process.

    Args:
        process: The Popen process to terminate.
    """
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()


def generate_synthetic_music(
    output_path: str | None = None,
    duration: float = 32.0,
    sr: int = 44100,
) -> str:
    """Generate synthetic music: C-F-G-Am chord progression with sine waves.

    Each chord plays for 2 seconds, looped to fill the duration.

    Args:
        output_path: Output WAV path. Defaults to temp file.
        duration: Duration in seconds.
        sr: Sample rate.

    Returns:
        Path to the generated WAV file.
    """
    if output_path is None:
        output_path = os.path.join(tempfile.gettempdir(), "calibration_music.wav")

    # Chord frequencies (root + third + fifth)
    chords = {
        "C":  [261.63, 329.63, 392.00],  # C4, E4, G4
        "F":  [349.23, 440.00, 523.25],  # F4, A4, C5
        "G":  [392.00, 493.88, 587.33],  # G4, B4, D5
        "Am": [440.00, 523.25, 659.25],  # A4, C5, E5
    }
    progression = ["C", "F", "G", "Am"]
    chord_duration = 2.0  # seconds per chord

    total_samples = int(duration * sr)
    signal = np.zeros(total_samples, dtype=np.float64)
    t_chord = np.arange(int(chord_duration * sr)) / sr

    # Amplitude envelope: gentle attack/release to avoid clicks
    envelope = np.ones_like(t_chord)
    attack = int(0.05 * sr)
    release = int(0.05 * sr)
    envelope[:attack] = np.linspace(0, 1, attack)
    envelope[-release:] = np.linspace(1, 0, release)

    sample_idx = 0
    chord_idx = 0
    while sample_idx < total_samples:
        chord_name = progression[chord_idx % len(progression)]
        freqs = chords[chord_name]

        # Generate chord (sum of sine waves)
        chord_signal = np.zeros_like(t_chord)
        for freq in freqs:
            chord_signal += 0.3 * np.sin(2 * np.pi * freq * t_chord)
        chord_signal *= envelope

        # Copy into output, handling end-of-buffer
        samples_to_copy = min(len(chord_signal), total_samples - sample_idx)
        signal[sample_idx:sample_idx + samples_to_copy] = chord_signal[:samples_to_copy]

        sample_idx += len(chord_signal)
        chord_idx += 1

    # Normalize to prevent clipping
    peak = np.max(np.abs(signal))
    if peak > 0:
        signal = signal / peak * 0.8

    sf.write(output_path, signal, sr, subtype="PCM_16")
    return output_path


def find_music_file() -> str | None:
    """Look for a music file in ~/Music/.

    Searches for common audio formats. Returns None if nothing found.
    """
    music_dir = Path.home() / "Music"
    if not music_dir.is_dir():
        return None

    extensions = ["*.mp3", "*.m4a", "*.wav", "*.flac", "*.aac", "*.ogg"]
    for ext in extensions:
        files = list(music_dir.glob(ext))
        if files:
            # Return the largest file (most likely a real song)
            files.sort(key=lambda f: f.stat().st_size, reverse=True)
            return str(files[0])

    return None


def get_music_file() -> str:
    """Get a music file for playback: real file from ~/Music/ or synthetic.

    Returns:
        Path to a playable WAV/audio file.
    """
    music = find_music_file()
    if music:
        return music
    return generate_synthetic_music()
