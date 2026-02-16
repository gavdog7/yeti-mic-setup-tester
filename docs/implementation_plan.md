# Implementation Plan — Blue Yeti Calibration Test Suite

## Task Tracking Legend
- `[ ]` — Not started
- `[~]` — In progress
- `[x]` — Complete
- `[!]` — Blocked / needs human review

---

## Phase A: Foundation & Core Utilities

### Task 1: Project scaffolding and dependencies
- **Status**: `[ ]`
- **Description**: Create directory structure, install dependencies, verify environment (Python, ffmpeg, sounddevice can see Yeti).
- **Acceptance**: All imports succeed. `sounddevice.query_devices()` runs. `ffmpeg -version` returns. Directory tree exists.
- **Evidence**: —

### Task 2: Audio analyzer module (`audio_analyzer.py`)
- **Status**: `[ ]`
- **Description**: Implement core analysis functions:
  - `calc_rms_dbfs(signal)` — RMS in dBFS
  - `calc_peak_dbfs(signal)` — Peak in dBFS
  - `speech_band_energy_ratio(signal, sr)` — 300Hz–3kHz energy ratio
  - `calc_snr(signal_rms_dbfs, noise_floor_dbfs)` — SNR in dB
  - `compute_spectrum(signal, sr)` — frequency/PSD for plotting
  - `dominant_freq_band(signal, sr)` — identify dominant frequency band
- **Acceptance**: Unit tests pass with known synthetic signals (sine waves, silence, noise).
- **Evidence**: —

### Task 3: Speaker playback module (`speaker_playback.py`)
- **Status**: `[ ]`
- **Description**: Implement:
  - `find_meeting_file()` — discover `.opus` files from granularSync, filter >5MB, sort by mtime
  - `convert_to_wav(opus_path)` — ffmpeg conversion to `/tmp/calibration_meeting.wav`
  - `play_audio(wav_path, volume=1.0)` — `afplay` subprocess, return process handle
  - `stop_audio(process)` — kill playback process
  - `generate_synthetic_music()` — C-F-G-Am chord progression sine waves, save as WAV
  - `find_music_file()` — look in `~/Music/` for a music file, fallback to synthetic
- **Acceptance**: Unit tests for file discovery logic (mocked). Manual test that afplay works.
- **Evidence**: —

---

## Phase B: Recording & Test Phases

### Task 4: Recording infrastructure
- **Status**: `[ ]`
- **Description**: Implement in `yeti_calibration.py`:
  - `select_yeti_device()` — auto-detect Blue Yeti, fallback to user selection
  - `record_phase(duration, device_index, label)` — record WAV, save to `recordings/run_XXX/`, return numpy array + filepath
  - `get_next_run_number()` — scan existing run directories
  - Run directory creation and management
- **Acceptance**: Can record a short (2s) clip and save it as WAV. File is valid and playable.
- **Evidence**: —

### Task 5: Terminal UX utilities
- **Status**: `[ ]`
- **Description**: Implement:
  - ANSI color helpers (red, green, yellow, cyan, bold)
  - Countdown timer ("3... 2... 1... RECORDING")
  - Live VU meter display during recording: `🔴 RECORDING Phase X [████████░░░░] -22.3 dBFS  7s left`
  - Phase boundary banners
  - Progress display
- **Acceptance**: Visual inspection of countdown and VU meter output in terminal.
- **Evidence**: —

### Task 6: Implement 5 test phases
- **Status**: `[ ]`
- **Description**: Implement each phase in `yeti_calibration.py`:
  - Phase 1: Silence Baseline (10s) — record silence, measure noise floor
  - Phase 2: Voice Only (15s) — display reading passage, record, measure voice levels
  - Phase 3: TV/Speaker Audio Only (30s) — play meeting recording, record Yeti pickup
  - Phase 4: Voice + TV Audio (30s) — play meeting recording + prompt user to speak
  - Phase 5: Voice + TV + Music (30s) — play meeting + music + prompt user to speak
  - Each phase stores results dict with RMS, peak, SNR, spectrum data
- **Acceptance**: All 5 phases execute sequentially without error. Recordings saved. Results dict populated.
- **Evidence**: —

### ⏸ HUMAN REVIEW CHECKPOINT 1
> **Review needed**: Run the tool end-to-end through all 5 phases with the actual Yeti mic and TV speakers. Verify recordings capture the intended audio. Check that the VU meter and prompts are clear and usable.

---

## Phase C: Analysis & Reporting

### Task 7: Report generator module (`report_generator.py`)
- **Status**: `[ ]`
- **Description**: Implement:
  - `generate_measurements_table(results)` — RMS, Peak, SNR, Dominant Freq Band per phase
  - `generate_recommendations(results)` — apply recommendation logic table from spec
  - `recommend_pattern(results)` — Cardioid / Omni / Bidirectional with reasoning
  - `recommend_positioning(results)` — distance, angle, placement advice
  - `generate_spectral_plots(results, output_dir)` — per-phase spectrum PNGs + overlay
  - `generate_report_markdown(results, run_number)` — full markdown report
  - `save_results_json(results, run_number)` — append to `yeti_calibration_results.json`
- **Acceptance**: Given mock phase results, generates valid markdown, correct recommendations, and readable plots.
- **Evidence**: —

### Task 8: Recommendation engine
- **Status**: `[ ]`
- **Description**: Implement the full recommendation logic table:
  - Noise floor assessment (gain too high / conservative)
  - Voice SNR assessment (too quiet / excellent)
  - Clipping risk detection
  - TV pickup assessment
  - Voice dominance ratio assessment
  - Pattern recommendation (Cardioid / Omni / Bidirectional)
  - Positioning recommendation
- **Acceptance**: Unit tests with edge-case result values produce correct recommendations per spec table.
- **Evidence**: —

---

## Phase D: Iterative Loop & Final Config

### Task 9: Iterative re-run loop
- **Status**: `[ ]`
- **Description**: After each run, prompt user:
  ```
  [A] Run ALL phases again
  [V] Re-run Voice Only (Phase 2) — quick gain check
  [S] Re-run TV Speakers Only (Phase 3) — pattern check
  [F] Re-run Full Mix (Phase 5) — final validation
  [Q] Quit — happy with settings
  ```
  Each re-run creates new `run_XXX/` subdirectory. Show comparison table vs previous runs (improvement/regression arrows).
- **Acceptance**: Can complete a run, choose re-run option, see comparison table, then quit.
- **Evidence**: —

### Task 10: Final config export and success criteria check
- **Status**: `[ ]`
- **Description**:
  - Check all success criteria (noise floor, voice SNR, TV SNR, dominance, clipping, music level)
  - If all pass → print green "✅ CALIBRATION COMPLETE"
  - Save to `~/.config/audio_calibration.json` with all required fields
  - If not all pass → show which criteria failed and suggest another run
- **Acceptance**: With mock data meeting criteria, config file is written correctly. With failing data, appropriate warnings shown.
- **Evidence**: —

### ⏸ HUMAN REVIEW CHECKPOINT 2
> **Review needed**: Full end-to-end test with real hardware. Verify recommendations are sensible. Check that the comparison table between runs is useful. Validate the exported config file.

---

## Phase E: Polish & Documentation

### Task 11: Error handling and edge cases
- **Status**: `[ ]`
- **Description**:
  - Yeti not connected → clear error message
  - No `.opus` files found → graceful fallback / message
  - ffmpeg not installed → helpful install instructions
  - Recording permission denied → guide user to System Preferences
  - Disk full / path issues → handle gracefully
  - Keyboard interrupt during recording → clean up processes
- **Acceptance**: Each error path tested (where possible) and produces a helpful message.
- **Evidence**: —

### Task 12: README and final documentation
- **Status**: `[ ]`
- **Description**: Create README.md with:
  - Quick start guide
  - Prerequisites
  - Usage examples
  - Troubleshooting
  - Architecture overview
- **Acceptance**: A new developer can follow README to install, run, and understand the tool.
- **Evidence**: —

### ⏸ HUMAN REVIEW CHECKPOINT 3 (Final)
> **Review needed**: Final review of complete tool. Test with real hardware in actual meeting recording workflow. Sign off on calibration quality.
