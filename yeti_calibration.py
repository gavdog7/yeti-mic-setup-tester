#!/usr/bin/env python3
from __future__ import annotations

"""Blue Yeti Microphone Calibration Test Suite.

Runs 5 test phases to calibrate a Blue Yeti USB microphone for optimal
recording of voice, TV speakers, and ambient audio on an M1 MacBook Pro.

Usage:
    python3 yeti_calibration.py
"""

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import sounddevice as sd
import soundfile as sf

import audio_analyzer as aa
import report_generator as rg
import speaker_playback as sp

# ──────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────

SAMPLE_RATE = 48000
CHANNELS = 1
SUBTYPE = "PCM_16"
RECORDINGS_DIR = "recordings"
REPORTS_DIR = "reports"

READING_PASSAGE = (
    '"The quarterly results show strong momentum across all business units. '
    "We're seeing particular growth in the enterprise segment, with several "
    "Fortune 500 clients expanding their deployments. I want to highlight "
    "three key metrics that demonstrate our value acceleration framework is "
    "working. First, time-to-value has decreased by forty percent. Second, "
    "customer expansion revenue is up thirty-two percent quarter over quarter. "
    "And third, our NPS score among enterprise accounts has hit an all-time "
    'high of seventy-eight."'
)

# ──────────────────────────────────────────────
# ANSI color helpers
# ──────────────────────────────────────────────

def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()

def red(text: str) -> str:
    return f"\033[91m{text}\033[0m" if _supports_color() else text

def green(text: str) -> str:
    return f"\033[92m{text}\033[0m" if _supports_color() else text

def yellow(text: str) -> str:
    return f"\033[93m{text}\033[0m" if _supports_color() else text

def cyan(text: str) -> str:
    return f"\033[96m{text}\033[0m" if _supports_color() else text

def bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _supports_color() else text

def dim(text: str) -> str:
    return f"\033[2m{text}\033[0m" if _supports_color() else text


# ──────────────────────────────────────────────
# Terminal UX
# ──────────────────────────────────────────────

def print_banner(text: str) -> None:
    """Print a phase banner."""
    width = 60
    print()
    print(cyan("=" * width))
    print(cyan(f"  {text}"))
    print(cyan("=" * width))
    print()


def print_separator() -> None:
    print(dim("-" * 60))


def countdown(seconds: int = 3) -> None:
    """Display a countdown before recording starts."""
    for i in range(seconds, 0, -1):
        print(f"  {bold(str(i))}...", end=" ", flush=True)
        time.sleep(1)
    print(red(bold("RECORDING")))
    print()


def vu_meter(level_dbfs: float, width: int = 30) -> str:
    """Generate a VU meter string from a dBFS level.

    Maps -60 dBFS to empty, 0 dBFS to full.
    """
    # Clamp to range
    clamped = max(-60.0, min(0.0, level_dbfs))
    filled = int((clamped + 60.0) / 60.0 * width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)

    if level_dbfs > -3:
        return red(bar)
    elif level_dbfs > -12:
        return yellow(bar)
    return green(bar)


# ──────────────────────────────────────────────
# Device selection
# ──────────────────────────────────────────────

def select_yeti_device() -> int:
    """Auto-detect Blue Yeti microphone, with fallback to manual selection.

    Returns:
        Device index for sounddevice.
    """
    devices = sd.query_devices()
    yeti_candidates = []

    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0 and "yeti" in dev["name"].lower():
            yeti_candidates.append((i, dev))

    if len(yeti_candidates) == 1:
        idx, dev = yeti_candidates[0]
        print(green(f"  Auto-detected: {dev['name']} (device {idx})"))
        return idx

    if len(yeti_candidates) > 1:
        print(yellow("  Multiple Yeti devices found:"))
        for idx, dev in yeti_candidates:
            print(f"    [{idx}] {dev['name']}")
        choice = input("  Enter device number: ").strip()
        return int(choice)

    # Fallback: show all input devices
    print(yellow("  Blue Yeti not auto-detected. Available input devices:"))
    input_devs = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]
    for idx, dev in input_devs:
        print(f"    [{idx}] {dev['name']} ({dev['max_input_channels']}ch)")

    choice = input("  Enter device number: ").strip()
    return int(choice)


def check_output_device() -> bool:
    """Warn if the system output device appears to be the Yeti (feedback risk).

    Uses macOS `system_profiler` to check the default output device.
    Returns True if safe, False if Yeti is the output device.
    """
    try:
        devices = sd.query_devices()
        default_out = sd.query_devices(sd.default.device[1])
        if "yeti" in default_out["name"].lower():
            print(red(bold("  WARNING: System output device is the Blue Yeti!")))
            print(red("  This will cause feedback during Phases 3-5."))
            print(red("  Please change output to MacBook speakers or LG TV in System Settings > Sound > Output."))
            resp = input("  Continue anyway? (y/N): ").strip().lower()
            return resp == "y"
    except Exception:
        pass
    return True


def check_macos_input_volume() -> None:
    """Remind user to check macOS input volume setting."""
    print(dim("  Tip: Set macOS input volume to ~80% (System Settings > Sound > Input)."))
    print(dim("  Use the physical gain knob on the Yeti for fine-tuning."))


# ──────────────────────────────────────────────
# Recording
# ──────────────────────────────────────────────

def get_next_run_number() -> int:
    """Scan existing run directories and return the next run number."""
    if not os.path.isdir(RECORDINGS_DIR):
        return 1
    existing = []
    for name in os.listdir(RECORDINGS_DIR):
        if name.startswith("run_") and os.path.isdir(os.path.join(RECORDINGS_DIR, name)):
            try:
                num = int(name.split("_")[1])
                existing.append(num)
            except (IndexError, ValueError):
                pass
    return max(existing, default=0) + 1


def record_phase(
    duration: float,
    device_index: int,
    label: str,
    run_dir: str,
) -> tuple[np.ndarray, str]:
    """Record audio from the Yeti with a live VU meter display.

    Args:
        duration: Recording duration in seconds.
        device_index: Sounddevice device index.
        label: Label for the recording (used in filename).
        run_dir: Directory to save the WAV file.

    Returns:
        Tuple of (numpy array of audio data, filepath to saved WAV).
    """
    os.makedirs(run_dir, exist_ok=True)
    filepath = os.path.join(run_dir, f"{label}.wav")
    total_frames = int(duration * SAMPLE_RATE)

    # Use a stream for real-time VU metering
    audio_buffer = np.zeros((total_frames, CHANNELS), dtype=np.float32)
    frames_written = [0]

    def callback(indata, frames, time_info, status):
        if status:
            pass  # Ignore xrun warnings during display
        start = frames_written[0]
        end = min(start + frames, total_frames)
        actual = end - start
        if actual > 0:
            audio_buffer[start:end] = indata[:actual]
            frames_written[0] = end

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        device=device_index,
        callback=callback,
        blocksize=2048,
    )

    start_time = time.time()
    with stream:
        while frames_written[0] < total_frames:
            elapsed = time.time() - start_time
            remaining = max(0, duration - elapsed)

            # Calculate current level for VU meter
            current_pos = frames_written[0]
            if current_pos > SAMPLE_RATE // 4:
                # Look at last 0.25s for responsive metering
                window_start = max(0, current_pos - SAMPLE_RATE // 4)
                window = audio_buffer[window_start:current_pos, 0]
                level = aa.calc_rms_dbfs(window)
            else:
                level = -60.0

            meter = vu_meter(level)
            status_line = (
                f"\r  {red('REC')} {label} [{meter}] "
                f"{level:6.1f} dBFS  {remaining:4.1f}s left"
            )
            print(status_line, end="", flush=True)
            time.sleep(0.1)

    print()  # Newline after VU meter

    # Trim to actual frames recorded
    actual_frames = frames_written[0]
    audio_data = audio_buffer[:actual_frames]

    # Save as WAV
    sf.write(filepath, audio_data, SAMPLE_RATE, subtype=SUBTYPE)
    print(dim(f"  Saved: {filepath}"))

    return audio_data.flatten(), filepath


# ──────────────────────────────────────────────
# Test phases
# ──────────────────────────────────────────────

def run_phase1(device_index: int, run_dir: str, results: dict) -> None:
    """Phase 1: Silence Baseline (10 seconds)."""
    print_banner("Phase 1: Silence Baseline")
    print("  Stay silent. Don't touch anything. No typing, no talking.")
    print("  Measuring noise floor for 10 seconds.")
    print()
    input(dim("  Press Enter when the room is quiet..."))
    print()
    countdown()

    audio, filepath = record_phase(10.0, device_index, "phase1_silence", run_dir)

    rms = aa.calc_rms_dbfs(audio)
    peak = aa.calc_peak_dbfs(audio)
    freqs, psd = aa.compute_spectrum(audio, SAMPLE_RATE)
    band = aa.dominant_freq_band(audio, SAMPLE_RATE)

    results["phase1"] = {
        "rms_dbfs": rms,
        "peak_dbfs": peak,
        "dominant_band": band,
        "speech_band_ratio": aa.speech_band_energy_ratio(audio, SAMPLE_RATE),
        "spectrum": {"freqs": freqs, "psd": psd},
        "filepath": filepath,
    }

    print()
    print(f"  Noise floor: {bold(f'{rms:.1f} dBFS')}")
    print(f"  Peak: {peak:.1f} dBFS")
    print(f"  Dominant band: {band}")

    if rms > -50:
        print(yellow("  >>> Noise floor is high. Consider reducing gain."))
    elif rms < -70:
        print(green("  >>> Very quiet. Headroom to increase gain if needed."))
    else:
        print(green("  >>> Noise floor looks good."))


def run_phase2(device_index: int, run_dir: str, results: dict) -> None:
    """Phase 2: Voice Only (15 seconds)."""
    print_banner("Phase 2: Voice Only")
    print("  You'll speak naturally at meeting volume for 15 seconds.")
    print("  Read this passage when recording starts:")
    print()
    print(cyan(f"  {READING_PASSAGE}"))
    print()
    print(dim("  (The passage is a guide — just speak naturally for 15 seconds)"))
    print()
    input(dim("  Press Enter when ready to speak..."))
    print()
    countdown()

    audio, filepath = record_phase(15.0, device_index, "phase2_voice", run_dir)

    noise_floor = results.get("phase1", {}).get("rms_dbfs", -96.0)
    rms = aa.calc_rms_dbfs(audio)
    peak = aa.calc_peak_dbfs(audio)
    snr = aa.calc_snr(rms, noise_floor)
    freqs, psd = aa.compute_spectrum(audio, SAMPLE_RATE)
    band = aa.dominant_freq_band(audio, SAMPLE_RATE)

    results["phase2"] = {
        "rms_dbfs": rms,
        "peak_dbfs": peak,
        "snr_db": snr,
        "dominant_band": band,
        "speech_band_ratio": aa.speech_band_energy_ratio(audio, SAMPLE_RATE),
        "spectrum": {"freqs": freqs, "psd": psd},
        "filepath": filepath,
    }

    print()
    print(f"  Voice RMS: {bold(f'{rms:.1f} dBFS')}")
    print(f"  Peak: {peak:.1f} dBFS")
    print(f"  SNR vs noise floor: {bold(f'{snr:.1f} dB')}")
    print(f"  Dominant band: {band}")

    if peak > -3:
        print(red("  >>> CLIPPING RISK! Reduce gain or move back."))
    if snr < 15:
        print(yellow("  >>> Voice too quiet. Increase gain or move closer."))
    elif snr > 40:
        print(green("  >>> Excellent voice isolation."))


def run_phase3(
    device_index: int, run_dir: str, results: dict,
    meeting_wav: str | None = None,
) -> None:
    """Phase 3: TV/Speaker Audio Only (30 seconds)."""
    print_banner("Phase 3: TV/Speaker Audio Only")

    if meeting_wav is None:
        print(yellow("  No meeting file available. Skipping playback."))
        print("  Recording room audio only...")
    else:
        print("  A meeting recording will play through your TV/speakers for 30 seconds.")
        print("  Stay SILENT — measuring TV/speaker pickup only.")

    print()
    print(bold("  IMPORTANT: The headphone volume knob (front bottom of Yeti) does NOT"))
    print(bold("  affect recordings. Only the gain knob (rear top) matters."))
    print()
    input(dim("  Press Enter when ready (stay silent during this phase)..."))
    print()
    countdown()

    # Start meeting playback
    playback_proc = None
    if meeting_wav:
        playback_proc = sp.play_audio(meeting_wav)

    try:
        audio, filepath = record_phase(30.0, device_index, "phase3_tv_audio", run_dir)
    finally:
        if playback_proc:
            sp.stop_audio(playback_proc)

    noise_floor = results.get("phase1", {}).get("rms_dbfs", -96.0)
    rms = aa.calc_rms_dbfs(audio)
    peak = aa.calc_peak_dbfs(audio)
    snr = aa.calc_snr(rms, noise_floor)
    freqs, psd = aa.compute_spectrum(audio, SAMPLE_RATE)
    band = aa.dominant_freq_band(audio, SAMPLE_RATE)

    results["phase3"] = {
        "rms_dbfs": rms,
        "peak_dbfs": peak,
        "snr_db": snr,
        "dominant_band": band,
        "speech_band_ratio": aa.speech_band_energy_ratio(audio, SAMPLE_RATE),
        "spectrum": {"freqs": freqs, "psd": psd},
        "filepath": filepath,
    }

    print()
    print(f"  TV pickup RMS: {bold(f'{rms:.1f} dBFS')}")
    print(f"  SNR vs noise floor: {bold(f'{snr:.1f} dB')}")
    print(f"  Speech band ratio: {results['phase3']['speech_band_ratio']:.1%}")

    if snr < 6:
        print(yellow("  >>> TV barely audible. Try Omnidirectional pattern or increase TV volume."))
    elif snr > 25:
        print(green("  >>> TV pickup is clear. Cardioid works."))


def run_phase4(
    device_index: int, run_dir: str, results: dict,
    meeting_wav: str | None = None,
) -> None:
    """Phase 4: Voice + TV Audio Simultaneously (30 seconds)."""
    print_banner("Phase 4: Voice + TV Audio")

    if meeting_wav is None:
        print(yellow("  No meeting file. Recording voice only (no TV comparison)."))
    else:
        print("  Meeting audio will play through your TV/speakers.")

    print("  Speak naturally while the meeting recording plays (30 seconds).")
    print("  React as you would in a real call — talk, pause, respond.")
    print()
    input(dim("  Press Enter when ready to speak..."))
    print()
    countdown()

    playback_proc = None
    if meeting_wav:
        playback_proc = sp.play_audio(meeting_wav)

    try:
        audio, filepath = record_phase(30.0, device_index, "phase4_voice_tv", run_dir)
    finally:
        if playback_proc:
            sp.stop_audio(playback_proc)

    noise_floor = results.get("phase1", {}).get("rms_dbfs", -96.0)
    rms = aa.calc_rms_dbfs(audio)
    peak = aa.calc_peak_dbfs(audio)
    snr = aa.calc_snr(rms, noise_floor)
    freqs, psd = aa.compute_spectrum(audio, SAMPLE_RATE)
    band = aa.dominant_freq_band(audio, SAMPLE_RATE)

    # Voice dominance: compare this phase's RMS vs Phase 3 (TV only)
    phase3_rms_linear = 10 ** (results.get("phase3", {}).get("rms_dbfs", -96.0) / 20.0)
    phase4_rms_linear = 10 ** (rms / 20.0)
    dominance = phase4_rms_linear / phase3_rms_linear if phase3_rms_linear > 0 else 0.0

    results["phase4"] = {
        "rms_dbfs": rms,
        "peak_dbfs": peak,
        "snr_db": snr,
        "dominant_band": band,
        "speech_band_ratio": aa.speech_band_energy_ratio(audio, SAMPLE_RATE),
        "voice_dominance_ratio": dominance,
        "spectrum": {"freqs": freqs, "psd": psd},
        "filepath": filepath,
    }

    print()
    print(f"  Combined RMS: {bold(f'{rms:.1f} dBFS')}")
    print(f"  Voice dominance ratio: {bold(f'{dominance:.1f}x')} over TV-only")

    if dominance < 1.5:
        print(yellow("  >>> Voice not dominant enough. Move mic closer."))
    elif dominance > 10:
        print(yellow("  >>> TV too quiet. Try Omni or reposition."))
    elif 2.0 <= dominance <= 5.0:
        print(green("  >>> Good voice/TV balance."))


def run_phase5(
    device_index: int, run_dir: str, results: dict,
    meeting_wav: str | None = None,
) -> None:
    """Phase 5: Sonos Music Isolation Test (15 seconds).

    Measures whether the Sonos (behind the TV, other side of the room) bleeds
    into the Yeti recording. Stay silent — this is a music-only pickup test.
    Includes a quick re-test loop to dial in the Sonos volume.
    """
    attempt = 0

    while True:
        attempt += 1
        suffix = f" (attempt {attempt})" if attempt > 1 else ""
        print_banner(f"Phase 5: Sonos Music Isolation Test{suffix}")

        print("  Measuring whether Sonos music bleeds into the Yeti recording.")
        print("  No TV audio. No speaking. Just Sonos music playing.")
        print()
        print(bold("  Before pressing Enter:"))
        print("  1. Start playing music on your Sonos at your normal listening volume")
        print("  2. Make sure the TV is quiet (no meeting playback)")
        print(dim("     (Sonos is behind the TV — ideally the mic won't pick it up)"))
        print()
        input(dim("  Press Enter when music is playing on Sonos (stay silent)..."))
        print()
        countdown()

        label = f"phase5_music_isolation{'_' + str(attempt) if attempt > 1 else ''}"
        audio, filepath = record_phase(15.0, device_index, label, run_dir)

        noise_floor = results.get("phase1", {}).get("rms_dbfs", -96.0)
        rms = aa.calc_rms_dbfs(audio)
        peak = aa.calc_peak_dbfs(audio)
        snr = aa.calc_snr(rms, noise_floor)
        freqs, psd = aa.compute_spectrum(audio, SAMPLE_RATE)
        band = aa.dominant_freq_band(audio, SAMPLE_RATE)

        # Music bleed: how much louder is this than the silence baseline?
        # Compare to voice energy from Phase 2 to express as a ratio
        voice_rms_linear = 10 ** (results.get("phase2", {}).get("rms_dbfs", -96.0) / 20.0)
        noise_rms_linear = 10 ** (noise_floor / 20.0)
        music_rms_linear = 10 ** (rms / 20.0)
        # Music contribution = anything above the noise floor
        music_contribution = max(0, music_rms_linear - noise_rms_linear)
        music_ratio = music_contribution / voice_rms_linear if voice_rms_linear > 0 else 0.0

        results["phase5"] = {
            "rms_dbfs": rms,
            "peak_dbfs": peak,
            "snr_db": snr,
            "dominant_band": band,
            "speech_band_ratio": aa.speech_band_energy_ratio(audio, SAMPLE_RATE),
            "music_energy_ratio": music_ratio,
            "music_snr_above_floor": snr,
            "spectrum": {"freqs": freqs, "psd": psd},
            "filepath": filepath,
        }

        print()
        print(f"  Music pickup RMS: {bold(f'{rms:.1f} dBFS')}")
        print(f"  Noise floor was: {noise_floor:.1f} dBFS")
        print(f"  Music above floor: {bold(f'{snr:.1f} dB')}")
        print(f"  Music as % of voice energy: {bold(f'{music_ratio:.0%}')}")

        if snr < 2.0:
            print(green("  >>> Sonos music is not being picked up. Virtually indistinguishable from silence."))
            break
        elif music_ratio <= 0.10:
            print(green(f"  >>> Music bleed is minimal ({music_ratio:.0%} of voice). Good Sonos volume."))
            break
        elif music_ratio <= 0.25:
            print(yellow(f"  >>> Some music pickup ({music_ratio:.0%} of voice), but within tolerance."))
            print(dim("     You could lower Sonos a bit for a cleaner recording, or keep it."))
        else:
            print(yellow(f"  >>> Music is bleeding into the recording ({music_ratio:.0%} of voice energy)."))
            print(yellow("  >>> Lower the Sonos volume and re-test."))

        # Offer quick re-test
        print()
        print(f"  {cyan('[R]')} Re-test — adjust Sonos volume and try again")
        print(f"  {cyan('[K]')} Keep this result and continue")
        choice = input("  Choice: ").strip().upper()
        if choice != "R":
            break
        print()
        print(dim("  Adjust your Sonos volume now..."))


# ──────────────────────────────────────────────
# Report generation
# ──────────────────────────────────────────────

def generate_run_report(
    results: dict[str, Any],
    run_number: int,
    previous_results: dict[str, Any] | None = None,
) -> str:
    """Generate report, plots, and save results for a run.

    Returns:
        Path to the generated markdown report.
    """
    report_dir = os.path.join(REPORTS_DIR, f"run_{run_number:03d}")
    plots_dir = os.path.join(report_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    # Generate spectral plots
    print(dim("  Generating spectral plots..."))
    rg.generate_spectral_plots(results, plots_dir)

    # Generate markdown report
    report_md = rg.generate_report_markdown(results, run_number, previous_results)
    report_path = os.path.join(report_dir, f"run_{run_number:03d}_report.md")
    with open(report_path, "w") as f:
        f.write(report_md)

    # Save JSON results
    rg.save_results_json(results, run_number)

    print(green(f"  Report saved: {report_path}"))
    return report_path


# ──────────────────────────────────────────────
# Success criteria display
# ──────────────────────────────────────────────

def display_success_criteria(results: dict[str, Any]) -> bool:
    """Display success criteria check and return whether all passed."""
    criteria = rg.check_success_criteria(results)
    all_passed = all(c["passed"] for c in criteria)

    print()
    print_banner("Success Criteria")

    for c in criteria:
        if c["passed"]:
            status = green("PASS")
        else:
            status = red("FAIL")
        print(f"  {status}  {c['name']}: {c['value']} (target: {c['target']})")

    print()
    if all_passed:
        print(green(bold("  CALIBRATION COMPLETE")))
        print(green("  All success criteria met!"))
    else:
        failed = [c["name"] for c in criteria if not c["passed"]]
        print(yellow(f"  Some criteria not met: {', '.join(failed)}"))
        print(yellow("  Consider running another calibration pass."))

    return all_passed


# ──────────────────────────────────────────────
# Display recommendations
# ──────────────────────────────────────────────

def display_recommendations(results: dict[str, Any]) -> None:
    """Display recommendations in the terminal."""
    recs = rg.generate_recommendations(results)
    pattern = rg.recommend_pattern(results)
    positioning = rg.recommend_positioning(results)

    print()
    print_banner("Recommendations")

    for rec in recs:
        if rec["severity"] == "danger":
            print(f"  {red('[!]')} {rec['action']}")
        elif rec["severity"] == "warning":
            print(f"  {yellow('[!]')} {rec['action']}")
        elif rec["severity"] == "pass":
            print(f"  {green('[+]')} {rec['action']}")
        else:
            print(f"  {dim('[i]')} {rec['action']}")

    print()
    print(f"  {bold('Recommended pattern')}: {cyan(pattern['pattern'])}")
    print(f"  {dim(pattern['reasoning'])}")

    print()
    print(f"  {bold('Positioning advice')}:")
    for line in positioning.split("\n"):
        print(f"  {line}")


# ──────────────────────────────────────────────
# Iterative loop
# ──────────────────────────────────────────────

def run_iterative_menu(
    device_index: int,
    results: dict[str, Any],
    run_number: int,
    meeting_wav: str | None,
) -> tuple[dict[str, Any], int]:
    """Present the re-run menu and execute chosen option.

    Returns:
        Updated (results, run_number).
    """
    while True:
        print()
        print_separator()
        print(bold("  What would you like to do?"))
        print()
        print(f"  {cyan('[T]')} Re-test Voice + TV (quick — the two key measurements)")
        print(f"  {cyan('[V]')} Re-run Voice Only (Phase 2)")
        print(f"  {cyan('[S]')} Re-run TV Speakers Only (Phase 3)")
        print(f"  {cyan('[M]')} Re-run Music Isolation (Phase 5) — Sonos volume check")
        print(f"  {cyan('[A]')} Run ALL phases (full suite)")
        print(f"  {cyan('[Q]')} Quit — happy with settings")
        print()

        choice = input("  Choice: ").strip().upper()

        if choice == "Q":
            return results, run_number

        previous_results = dict(results)
        run_number += 1
        run_dir = os.path.join(RECORDINGS_DIR, f"run_{run_number:03d}")

        if choice == "T":
            run_quick_voice_tv(device_index, run_dir, results, meeting_wav)
        elif choice == "V":
            run_phase2(device_index, run_dir, results)
            _infer_dominance(results)
        elif choice == "S":
            run_phase3(device_index, run_dir, results, meeting_wav)
            _infer_dominance(results)
        elif choice == "M":
            run_phase5(device_index, run_dir, results, meeting_wav)
        elif choice == "A":
            run_all_phases(device_index, run_dir, results, meeting_wav)
        else:
            print(yellow("  Invalid choice. Please try again."))
            run_number -= 1
            continue

        # Generate report and show results
        generate_run_report(results, run_number, previous_results)

        # Show comparison
        print()
        print_banner("Comparison with Previous Run")
        comparison = rg.generate_comparison_table(results, previous_results)
        for line in comparison.split("\n"):
            print(f"  {line}")

        display_recommendations(results)
        display_success_criteria(results)

    return results, run_number


def run_core_phases(
    device_index: int,
    run_dir: str,
    results: dict[str, Any],
    meeting_wav: str | None,
) -> None:
    """Run the core test phases: Silence, Voice, TV.

    Dominance is inferred from Phase 2 (voice) vs Phase 3 (TV) directly,
    without needing a separate combined Phase 4 recording.
    """
    run_phase1(device_index, run_dir, results)
    run_phase2(device_index, run_dir, results)
    run_phase3(device_index, run_dir, results, meeting_wav)

    # Infer voice dominance from Phase 2 vs Phase 3
    _infer_dominance(results)


def run_quick_voice_tv(
    device_index: int,
    run_dir: str,
    results: dict[str, Any],
    meeting_wav: str | None,
) -> None:
    """Quick re-test: just Voice (Phase 2) and TV (Phase 3).

    Reuses the existing noise floor from Phase 1.
    """
    run_phase2(device_index, run_dir, results)
    run_phase3(device_index, run_dir, results, meeting_wav)
    _infer_dominance(results)


def _infer_dominance(results: dict[str, Any]) -> None:
    """Calculate voice dominance ratio from Phase 2 and Phase 3 results.

    Compares voice-only RMS to TV-only RMS to estimate how much louder
    the voice is than the TV speakers in the recording.
    """
    p2 = results.get("phase2", {})
    p3 = results.get("phase3", {})
    if not p2 or not p3:
        return

    voice_rms_linear = 10 ** (p2.get("rms_dbfs", -96.0) / 20.0)
    tv_rms_linear = 10 ** (p3.get("rms_dbfs", -96.0) / 20.0)
    dominance = voice_rms_linear / tv_rms_linear if tv_rms_linear > 0 else 0.0

    # Store in phase4 slot so the report generator and success criteria work
    results["phase4"] = {
        "rms_dbfs": p2.get("rms_dbfs", -96.0),
        "peak_dbfs": p2.get("peak_dbfs", -96.0),
        "snr_db": p2.get("snr_db", 0.0),
        "dominant_band": p2.get("dominant_band", "—"),
        "speech_band_ratio": p2.get("speech_band_ratio", 0.0),
        "voice_dominance_ratio": dominance,
        "inferred": True,
    }

    print()
    print_separator()
    print(f"  Voice dominance (inferred): {bold(f'{dominance:.1f}x')} voice over TV")
    if dominance < 1.5:
        print(yellow("  >>> Voice not dominant enough over TV audio."))
    elif dominance > 10:
        print(yellow("  >>> TV too quiet relative to voice."))
    elif 2.0 <= dominance <= 5.0:
        print(green("  >>> Good voice/TV balance."))
    print()


def run_all_phases(
    device_index: int,
    run_dir: str,
    results: dict[str, Any],
    meeting_wav: str | None,
) -> None:
    """Run all 5 test phases (full suite)."""
    run_phase1(device_index, run_dir, results)
    run_phase2(device_index, run_dir, results)
    run_phase3(device_index, run_dir, results, meeting_wav)
    _infer_dominance(results)
    run_phase4(device_index, run_dir, results, meeting_wav)
    run_phase5(device_index, run_dir, results, meeting_wav)


# ──────────────────────────────────────────────
# Meeting file setup
# ──────────────────────────────────────────────

def setup_meeting_file() -> str | None:
    """Prepare a meeting clip with confirmed speech content for playback.

    Uses a pre-selected meeting file known to contain clear speech,
    extracted from a speech-heavy section. No user interaction needed.
    """
    print(dim("  Preparing meeting audio clip (with speech content)..."))

    wav_path = sp.prepare_calibration_meeting_clip()
    if wav_path is None:
        print(yellow("  Could not prepare meeting audio."))
        print(yellow("  Phases 3-5 will record room audio without meeting playback."))
        return None

    print(green(f"  Ready: {wav_path}"))
    return wav_path


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main() -> None:
    print()
    print(bold(cyan("  Blue Yeti Microphone Calibration Test Suite")))
    print(dim("  ─────────────────────────────────────────────"))
    print()

    # ── Preflight checks ──
    print(bold("  Preflight Checks"))
    print_separator()

    # Check Yeti device
    print()
    print(dim("  Detecting Blue Yeti..."))
    try:
        device_index = select_yeti_device()
    except (ValueError, IndexError) as e:
        print(red(f"  Could not select device: {e}"))
        print(red("  Make sure the Blue Yeti is plugged in and recognized by macOS."))
        sys.exit(1)

    # Check output device isn't Yeti
    if not check_output_device():
        sys.exit(1)

    # Remind about macOS input volume
    check_macos_input_volume()

    # Check mute button
    print()
    print(bold("  Yeti Hardware Checklist:"))
    print("  - Mute button (front, top): LED should be OFF (unmuted)")
    print("  - Gain knob (rear, top): Start at ~30%")
    print("  - Pattern (rear, bottom): Start with Cardioid (heart symbol)")
    print("  - Headphone volume (front, bottom): This does NOT affect recording")
    print()
    print(bold("  LG TV / Speaker Settings:"))
    print("  - TV volume: start at 15 (reduced from 20 to improve voice dominance)")
    print("  - Make sure the TV speakers are the active audio output on the TV")
    print()
    print(bold("  Sonos (for Phase 5 only):"))
    print("  - Music will play from your Sonos (behind TV, other side of room)")
    print("  - Have music ready to play but don't start it yet — Phase 5 will prompt you")
    print()
    input(dim("  Press Enter when ready to begin..."))

    # ── Setup meeting file ──
    print()
    print(bold("  Meeting File Setup"))
    print_separator()
    meeting_wav = setup_meeting_file()

    # ── Run core phases (Silence + Voice + TV) ──
    run_number = get_next_run_number()
    run_dir = os.path.join(RECORDINGS_DIR, f"run_{run_number:03d}")
    results: dict[str, Any] = {}

    try:
        run_core_phases(device_index, run_dir, results, meeting_wav)
    except KeyboardInterrupt:
        print()
        print(yellow("\n  Recording interrupted. Saving partial results..."))

    # ── Generate report ──
    print()
    print(bold("  Generating Report"))
    print_separator()
    report_path = generate_run_report(results, run_number)

    # ── Display results ──
    display_recommendations(results)
    all_passed = display_success_criteria(results)

    # ── Iterative loop ──
    if not all_passed:
        results, run_number = run_iterative_menu(
            device_index, results, run_number, meeting_wav
        )

    # ── Final config export ──
    criteria = rg.check_success_criteria(results)
    all_passed = all(c["passed"] for c in criteria)

    if all_passed:
        pattern = rg.recommend_pattern(results)
        config_path = rg.save_final_config(
            results,
            device_index=device_index,
            recommended_pattern=pattern["pattern"],
        )
        print()
        print(green(bold("  Final config saved to: ") + config_path))
        print(green("  This config will be used by GranularSync and WhisperFlow."))
    else:
        print()
        print(yellow("  Calibration not yet complete. Run again to fine-tune settings."))
        resp = input("  Save current config anyway? (y/N): ").strip().lower()
        if resp == "y":
            pattern = rg.recommend_pattern(results)
            config_path = rg.save_final_config(
                results,
                device_index=device_index,
                recommended_pattern=pattern["pattern"],
            )
            print(green(f"  Config saved: {config_path}"))

    print()
    print(dim("  Done. See reports/ for detailed analysis."))
    print()


if __name__ == "__main__":
    # Handle Ctrl+C gracefully
    signal.signal(signal.SIGINT, lambda s, f: (print(yellow("\n  Interrupted.")), sys.exit(0)))
    main()
