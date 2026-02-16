# CLAUDE.md — Blue Yeti Microphone Calibration Test Suite

## Project Overview
Python CLI tool (`yeti_calibration.py`) that runs 5 test phases to calibrate a Blue Yeti USB microphone for optimal recording of voice, TV speakers (meeting participants), and ambient audio on an M1 MacBook Pro.

## Environment
- **Machine**: MacBook Pro M1, macOS, full admin access
- **Microphone**: Blue Yeti USB
- **Python**: System python3 with `pip install --break-system-packages`
- **FFmpeg**: Via `brew install ffmpeg`
- **Meeting recordings**: `/Volumes/4TBSSD/granularSync/` (4TB SSD, `.opus` files)

## Key Commands
```bash
# Install dependencies
pip install --break-system-packages sounddevice soundfile numpy scipy matplotlib

# Install ffmpeg if needed
brew install ffmpeg

# Run the calibration tool
python3 yeti_calibration.py

# Run tests
python3 -m pytest tests/ -v
```

## Project Structure
```
yeti_calibration/
├── yeti_calibration.py      # Main CLI entry point & test phase orchestrator
├── audio_analyzer.py        # RMS, SNR, spectral analysis functions
├── speaker_playback.py      # Meeting file discovery, ffmpeg conversion, afplay playback
├── report_generator.py      # Markdown reports, matplotlib plots, JSON results
├── recordings/run_XXX/      # WAV recordings per run
├── reports/run_XXX_report.md # Per-run reports + plots/
└── yeti_calibration_results.json  # Accumulated results across runs
```

## Blue Yeti Hardware Controls
The calibration tool must be aware of all user-configurable controls on the Yeti and guide the user through adjusting them between runs. See `docs/instructions.md` for the full control matrix.

- **Gain knob** (rear, top): Analog preamp sensitivity, 0–100% (CCW=min, CW=max). Primary recording level control. Start at ~25–35% for voice at 6–12".
- **Pattern selector** (rear, bottom): 4 positions — Cardioid (default, best voice isolation), Omnidirectional (if TV too quiet), Bidirectional (mic between user and TV), Stereo (not recommended for this workflow).
- **Mute button** (front, top): Must be unmuted (LED off) to record.
- **Headphone volume** (front, bottom): Monitor-only, does NOT affect recording levels. Tool should warn users not to confuse this with gain.
- **macOS input volume** (System Settings > Sound > Input): Digital input level. Set to ~80% as stable baseline; use hardware gain knob for fine-tuning. Tool should verify this at startup.
- **macOS output device**: Must NOT be Yeti during Phases 3–5 to avoid feedback loops. Tool should verify at startup.

## Architecture Decisions
- **Recording**: `sounddevice.rec()` at 48kHz, 16-bit, mono
- **Playback**: `subprocess.Popen(['afplay', filepath])` for system speakers — never route through Yeti
- **Device selection**: Auto-detect "Yeti" via `sounddevice.query_devices()`, fallback to numbered list
- **Meeting file discovery**: Glob for `.opus` in granularSync directory, filter >5MB, sort by mtime desc
- **Music**: Use file from `~/Music/` or generate synthetic (C-F-G-Am chord progression, sine waves)

## Implementation Plan
See `docs/implementation_plan.md` for the task-by-task implementation plan with status tracking.

## Success Criteria
| Metric | Target |
|--------|--------|
| Noise floor | < -55 dBFS |
| Voice SNR | > 20 dB |
| TV speaker SNR | > 6 dB |
| Voice dominance over TV | 2x – 5x |
| No clipping | Peak < -3 dBFS |
| Music level | < 25% of voice energy |

## Conventions
- Python 3.9+ (uses `from __future__ import annotations` for modern type hints)
- Type hints on public functions
- Docstrings on modules and classes
- ANSI color output for terminal UX
- All recordings saved as WAV
- Results persisted in JSON for cross-run comparison

## Final Config Export
When calibration passes, save to `~/.config/audio_calibration.json` for consumption by GranularSync and WhisperFlow.
