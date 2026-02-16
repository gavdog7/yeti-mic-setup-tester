The file tools are having issues right now, so here's the complete self-contained prompt you can copy and hand to your developer. It's long but comprehensive — everything they need is here:

Blue Yeti Microphone Calibration Test Suite — Developer Prompt
Context
You are working on Gavin's M1 MacBook Pro (personal laptop). A Blue Yeti USB microphone is plugged into this machine. Build a calibration/test tool that helps tune the Yeti's physical settings and placement to optimally capture:

Gavin's voice (primary — clear and dominant)
Room audio from LG TV speakers (secondary — meeting participants' voices played through the TV, must be audible/intelligible)
Ambient music or room sounds (present but not overwhelming)

This is for a meeting recording workflow where work calls happen on a separate M3 MacBook Pro, with call audio routed to LG TV/monitor speakers. The M1 records everything via GranularSync using the Yeti.
Environment

Machine: MacBook Pro M1 (personal, full admin access)
Microphone: Blue Yeti USB (plugged into M1)
Meeting recordings: /media/storage/4TBSSD/granularSync/ — mounted 4TB SSD. Browse dated folders for .opus recording files. Pick one >5MB and >2 minutes.
Python: Available. Install with pip install --break-system-packages <package>
FFmpeg: Available or install via brew install ffmpeg

What to Build
Python CLI tool: yeti_calibration.py — runs test phases, records from Yeti during each, analyzes results, provides actionable Yeti settings feedback.
Dependencies
bashpip install --break-system-packages sounddevice soundfile numpy scipy matplotlib
```

---

## 5 Test Phases

### Phase 1: Silence Baseline (10 seconds)
- **Prompt**: "Stay silent. Don't touch anything. Measuring noise floor."
- **Measures**: Background noise RMS, peak, spectral profile
- **Output**: Noise floor in dBFS, frequency spectrum

### Phase 2: Voice Only (15 seconds)
- **Prompt**: "Speak naturally at meeting volume. Read this passage:"

> "The quarterly results show strong momentum across all business units. We're seeing particular growth in the enterprise segment, with several Fortune 500 clients expanding their deployments. I want to highlight three key metrics that demonstrate our value acceleration framework is working. First, time-to-value has decreased by forty percent. Second, customer expansion revenue is up thirty-two percent quarter over quarter. And third, our NPS score among enterprise accounts has hit an all-time high of seventy-eight."

- **Measures**: Voice RMS, peak, SNR vs Phase 1 noise floor, frequency range
- **Output**: Voice level dBFS, SNR ratio, voice frequency band ID

### Phase 3: TV/Speaker Audio Only (30 seconds)
- **Setup**: Find a real `.opus` meeting file from `/media/storage/4TBSSD/granularSync/` (sort by size desc, pick >5MB), convert to WAV via `ffmpeg -i input.opus -ar 44100 -ac 1 /tmp/calibration_meeting.wav`, play through system speakers via `subprocess.Popen(['afplay', filepath])`
- **Prompt**: "Stay silent. Meeting recording plays through your speakers. Measuring TV pickup."
- **Measures**: Speaker audio RMS via Yeti, SNR vs noise floor, speech band energy (300Hz–3kHz)
- **Output**: Speaker pickup level, intelligibility estimate

### Phase 4: Voice + TV Audio Simultaneously (30 seconds)
- **Setup**: Play same meeting WAV through speakers again
- **Prompt**: "Speak naturally while the meeting recording plays. React as you would in a real call."
- **Measures**: Overall RMS, voice-to-speaker ratio (compare against Phase 2/3 baselines), voice dominance
- **Output**: Voice dominance ratio, balance assessment

### Phase 5: Voice + TV Audio + Background Music (30 seconds)
- **Setup**: Play meeting recording + either a music file from `~/Music/` or generate synthetic music (chord progression: C-F-G-Am, 2sec each, looped, sine waves). Play music at 50% volume via second `afplay --volume 0.5`
- **Prompt**: "Speak while meeting audio and music play. Most complex scenario."
- **Measures**: Overall levels, voice vs combined background, spectral separation
- **Output**: Voice-to-background ratio, overall assessment

---

## Analysis & Recommendations

### Measurements Table
Generate a table with RMS (dBFS), Peak (dBFS), SNR vs Floor, and Dominant Freq Band for each phase.

### Blue Yeti Hardware Controls & Configuration

The Blue Yeti has four physical controls and one software-level setting. The calibration tool must account for all of them when making recommendations.

#### Front Controls

| Control | Location | Function | Affects Recording? |
|---------|----------|----------|-------------------|
| **Mute button** | Front, top | Toggle mic on/off (red LED = muted) | Yes — must be unmuted to record |
| **Headphone volume knob** | Front, bottom | Adjusts headphone monitor output level | **No** — purely monitoring, does not affect the recorded signal |

The headphone volume knob controls the 3.5mm headphone jack on the mic's base. It's for real-time monitoring only. The calibration tool should note this in user prompts so users don't confuse it with gain.

#### Rear Controls

| Control | Location | Function | Affects Recording? |
|---------|----------|----------|-------------------|
| **Gain knob** | Rear, top | Controls mic sensitivity / preamp level (CCW = 0%, CW = 100%) | **Yes** — primary recording level control |
| **Pattern selector knob** | Rear, bottom | Selects one of four polar pickup patterns | **Yes** — determines directional sensitivity |

##### Gain Knob Detail
- Unmarked continuous knob. Fully counter-clockwise = minimum sensitivity, fully clockwise = maximum.
- **Interaction with macOS input volume**: The gain knob controls analog preamp level *before* the ADC. macOS System Settings > Sound > Input volume controls the *digital* input level. Both affect the final recorded signal. The recommended approach is:
  1. Set macOS input volume to ~80% as a stable baseline.
  2. Use the physical gain knob as the primary adjustment — it provides better signal-to-noise ratio when set higher with the source close, vs. boosting digitally.
  3. For voice recording at 6–12 inches, start at ~25–35% gain and adjust until peaks hit around -12 dB to -6 dB in the calibration tool's VU meter.
- **Too much gain**: Picks up excessive background noise, increases noise floor, risks clipping.
- **Too little gain**: Voice is quiet, low SNR, digital boosting introduces noise.

##### Pattern Selector Detail
The knob clicks between four positions. Align the indicator line with the symbol on the mic body.

| Pattern | Symbol | Pickup Shape | Best For | Use In Calibration |
|---------|--------|-------------|----------|-------------------|
| **Cardioid** | ♥ (heart) | Front only, rejects sides/rear | Solo voice, podcasting, calls — **default recommendation** | Phase 2 (voice), Phase 4/5 (voice+TV if TV is behind mic) |
| **Omnidirectional** | ○ (circle) | Equal pickup from all directions | Room recording, roundtable, capturing TV + voice equally | Phase 3 (TV pickup test), fallback if TV SNR too low in cardioid |
| **Bidirectional** | ∞ (figure-8) | Front + rear, rejects sides | Two people facing each other, mic between user and TV | Phase 4 alternative if mic is positioned between user and TV speakers |
| **Stereo** | ⟺ (L/R arrows) | Left + right channels | Music, ASMR, spatial audio | Phase 5 (music test) or not recommended for this workflow |

**Pattern recommendation logic for this project:**
1. **Start with Cardioid** — best voice isolation, lowest noise floor, most likely winner.
2. **Try Omnidirectional** if Phase 3 TV speaker SNR < 6 dB in cardioid — omni picks up room sound evenly.
3. **Try Bidirectional** if the mic physically sits between the user and TV — captures both directions while rejecting side noise.
4. **Stereo is generally not recommended** for this meeting-recording workflow (mono is preferred for speech intelligibility).

#### macOS Software Settings

| Setting | Location | Recommended Value | Notes |
|---------|----------|-------------------|-------|
| **Input device** | System Settings > Sound > Input | "Yeti Stereo Microphone" | Must be selected; tool auto-detects via `sounddevice` |
| **Input volume** | System Settings > Sound > Input slider | ~80% | Stable baseline; let the hardware gain knob do the fine-tuning |
| **Sample rate** | Audio MIDI Setup (or via `sounddevice`) | 48000 Hz | Match project recording settings |
| **Output device** | System Settings > Sound > Output | MacBook speakers or LG TV | Must NOT be the Yeti — playback must go through room speakers |

**Important**: The calibration tool should verify at startup that the system output device is NOT the Yeti, to avoid feedback loops during Phases 3–5.

#### Calibration-Aware Control Matrix

The tool should guide users through adjusting these controls across runs:

| If This Happens... | Adjust This Control | Direction |
|--------------------|--------------------|-----------|
| Noise floor too high (> -50 dBFS) | Gain knob | Turn CCW (reduce) |
| Noise floor very low (< -70 dBFS) | Gain knob | Room to turn CW (increase) |
| Voice too quiet (SNR < 15 dB) | Gain knob OR distance | Increase gain OR move mic closer (6–10") |
| Clipping detected (peak > -3 dBFS) | Gain knob OR distance | Reduce gain OR move back |
| TV barely audible (SNR < 6 dB) | Pattern selector | Switch from Cardioid → Omnidirectional |
| TV too loud / voice not dominant | Pattern selector | Switch from Omni → Cardioid |
| Voice not dominant enough (ratio < 1.5x) | Distance + Gain | Move mic closer to mouth, adjust gain |
| Voice way too dominant (ratio > 10x) | Pattern selector or TV volume | Try Omni, or increase TV volume |

Between re-runs, the tool should tell the user exactly which knob to turn and in which direction, referencing the physical control by name and location (e.g., "Turn the **gain knob on the back of the Yeti** counter-clockwise about 20%").

### Recommendation Logic

| Condition | Recommendation |
|-----------|---------------|
| Phase 1 RMS > -50 dBFS | "Reduce gain. Turn rear knob CCW." |
| Phase 1 RMS < -70 dBFS | "Gain is conservative. Headroom to increase." |
| Phase 2 SNR < 15 dB | "Voice too quiet. Increase gain or move mic closer (6–10in)." |
| Phase 2 SNR > 40 dB | "Excellent voice isolation." |
| Phase 2 peak > -3 dBFS | "Clipping risk! Reduce gain or move back." |
| Phase 3 SNR < 6 dB | "TV barely audible. Try Omnidirectional pattern or increase TV volume." |
| Phase 3 SNR > 25 dB | "TV pickup is clear. Cardioid works." |
| Phase 4 ratio < 1.5x | "Voice not dominant enough. Move mic closer." |
| Phase 4 ratio > 10x | "TV too quiet. Try Omni or reposition mic." |
| Phase 4 ratio 2x–5x | "Good balance." |

### Pattern Recommendation
Recommend ONE of Cardioid (most likely), Omnidirectional (if TV too quiet), or Bidirectional (if mic between Gavin and TV) with reasoning.

### Positioning Recommendation
Distance from mouth, angle, placement relative to TV.

### Spectral Plots
Save matplotlib PNGs: each phase's spectrum + an all-phases overlay comparison.

---

## Iterative Loop

After each run, prompt:
```
[A] Run ALL phases again
[V] Re-run Voice Only (Phase 2) — quick gain check
[S] Re-run TV Speakers Only (Phase 3) — pattern check
[F] Re-run Full Mix (Phase 5) — final validation
[Q] Quit — happy with settings
Each re-run: new run_XXX/ subdirectory, comparison table vs previous runs showing improvement/regression. All results saved to yeti_calibration_results.json.

Implementation Details
Device Selection
sounddevice.query_devices() — auto-select "Yeti", fallback to numbered list.
Recording: 16-bit WAV, 48kHz, mono, via sounddevice.rec()
Playback: subprocess.Popen(['afplay', filepath]) for system speakers. Kill process when phase ends. Never route through Yeti.
Meeting File Discovery
pythonimport glob, os
opus_files = glob.glob('/media/storage/4TBSSD/granularSync/**/*.opus', recursive=True)
opus_files = [f for f in opus_files if os.path.getsize(f) > 5_000_000]
opus_files.sort(key=lambda f: os.path.getmtime(f), reverse=True)
Terminal UX

ANSI colors, countdown timers ("3... 2... 1... RECORDING")
Live VU meter: 🔴 RECORDING Phase 2 [████████░░░░] -22.3 dBFS  7s left
Clear phase boundaries

Analysis Functions
pythondef calc_rms_dbfs(signal):
    rms = np.sqrt(np.mean(signal.astype(np.float64) ** 2))
    return 20 * np.log10(rms) if rms > 0 else -96.0

def speech_band_energy_ratio(signal, sr):
    freqs, psd = welch(signal, fs=sr, nperseg=4096)
    speech = (freqs >= 300) & (freqs <= 3000)
    return np.sum(psd[speech]) / np.sum(psd)
```

---

## Output Files
```
yeti_calibration/
├── yeti_calibration.py
├── audio_analyzer.py
├── speaker_playback.py
├── report_generator.py
├── recordings/run_001/*.wav
├── reports/run_001_report.md + plots/
└── yeti_calibration_results.json
Final Config Export
When satisfied, save to ~/.config/audio_calibration.json:
json{
  "preferred_input_device": "Blue Yeti",
  "device_index": 3,
  "sample_rate": 48000,
  "channels": 1,
  "recommended_gain_percent": 40,
  "recommended_pattern": "Cardioid",
  "recommended_distance_inches": 8,
  "noise_floor_dbfs": -62.3,
  "voice_snr_db": 40.2,
  "calibrated_at": "2026-02-16T12:00:00"
}
This config will be consumed by GranularSync and WhisperFlow for mic selection.
Success Criteria
MetricTargetNoise floor< -55 dBFSVoice SNR> 20 dBTV speaker SNR> 6 dBVoice dominance over TV2x – 5xNo clippingPeak < -3 dBFSMusic level< 25% of voice energy
When all met → print green "✅ CALIBRATION COMPLETE" and save config.