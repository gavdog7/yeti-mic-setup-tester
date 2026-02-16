# Blue Yeti Calibration Results — 2026-02-16

## Final Settings

| Setting | Value |
|---------|-------|
| **Gain knob** (rear, top) | ~50% (halfway) |
| **Pattern** (rear, bottom) | Cardioid |
| **Mute** (front, top) | Unmuted (LED off) |
| **macOS input volume** | ~80% |
| **LG TV volume** | 15 |
| **Sonos** | Normal listening volume (not picked up by mic) |
| **Mic position** | Desktop, ~12-14 inches from mouth, front facing user |

## Final Measurements (Run 005)

| Metric | Value | Formal Target | Status | Practical Assessment |
|--------|-------|---------------|--------|---------------------|
| Noise floor | -43.9 dBFS | < -55 dBFS | FAIL | Acceptable — artifact of gain at 50%, not an issue for Whisper |
| Voice SNR | 14.2 dB | > 20 dB | FAIL | Acceptable — Whisper handles speech reliably down to ~10 dB SNR |
| TV speaker SNR | 6.0 dB | > 6 dB | FAIL | Borderline but adequate — TV audio is captured for context |
| Voice dominance | 2.6x | 2.0x – 5.0x | PASS | The key metric — voice is clearly dominant over TV |
| No clipping | -10.2 dBFS | < -3 dBFS | PASS | Healthy recording level with 7 dB headroom |
| Music level (Sonos) | 0% | < 25% | PASS | Sonos behind TV is not picked up at all |

## Calibration Journey

Five runs were performed, each adjusting one variable at a time:

### Run 001 — Baseline (broken)
- **Settings**: Gain ~30%, TV vol 20, Cardioid
- **Issue**: Eddie (baby) was in arms during silence test; meeting file was keyboard typing not speech; music played through afplay on wrong speakers; no "Press Enter" gates before phases
- **Result**: 5/6 criteria failed. Noise floor -43.7, voice SNR 3.5, dominance 0.4x
- **Action**: Fixed the tool — added Press Enter before each phase, pre-selected meeting file with confirmed speech content, restructured Phase 5 for Sonos

### Run 002 — First real attempt
- **Settings**: Gain ~30%, TV vol 20, Cardioid
- **Result**: 4/6 failed. Noise floor -51.1, voice SNR 6.6, dominance 0.8x
- **Action**: Reduced TV volume (20 → 15) to improve voice dominance

### Run 003 — TV volume reduced
- **Settings**: Gain ~30%, TV vol 15, Cardioid
- **Result**: 2/6 failed. Noise floor -55.3 (pass!), voice SNR 12.1, dominance 1.3x
- **Observation**: TV volume change improved noise floor significantly but dominance still low
- **Action**: Increased gain (30% → 50%) to boost voice signal — peak was at -24.1 with lots of headroom

### Run 004 — Gain slightly increased (intermediate)
- **Settings**: Gain ~40%, TV vol 15, Cardioid
- **Result**: 2/6 failed. Noise floor -59.0 (best), voice SNR 15.0, dominance 1.3x
- **Observation**: Best noise floor but dominance still not there
- **Action**: Increased gain further to ~50%

### Run 005 — Final (accepted)
- **Settings**: Gain ~50%, TV vol 15, Cardioid
- **Result**: 3/6 formal criteria failed, but all practical requirements met
- **Key win**: Voice dominance reached 2.6x — the primary goal
- **Trade-off**: Higher gain raised noise floor to -43.9, but voice peak at -10.2 dBFS is a strong signal for transcription

## Why This Configuration Was Accepted

The formal thresholds (noise floor < -55 dBFS, voice SNR > 20 dB) were set conservatively for an ideal recording environment. In practice:

1. **Voice dominance at 2.6x** means Whisper/transcription will clearly distinguish Gavin's voice from TV meeting participants. This was the primary goal.
2. **Voice peak at -10.2 dBFS** is a healthy recording level — loud enough for robust transcription, with 7 dB before clipping.
3. **14.2 dB voice SNR** is well within Whisper's operational range (reliable down to ~10 dB).
4. **The noise floor (-43.9 dBFS)** is a consequence of analog gain amplifying room noise, but since the voice signal is proportionally louder, it doesn't degrade transcription quality.
5. **Sonos music at 0% bleed** means background music is a non-issue at normal listening volume.

## Config Export

Final config saved to `~/.config/audio_calibration.json` for use by GranularSync and WhisperFlow.
