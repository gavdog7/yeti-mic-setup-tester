from __future__ import annotations

"""Report generation and recommendation engine for Blue Yeti calibration.

Generates markdown reports, spectral plots, JSON results, and
actionable recommendations for Yeti hardware settings.
"""

import json
import os
from datetime import datetime
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

from audio_analyzer import calc_snr


# ──────────────────────────────────────────────
# Success criteria thresholds
# ──────────────────────────────────────────────

THRESHOLDS = {
    "noise_floor_max": -55.0,      # dBFS
    "voice_snr_min": 20.0,         # dB
    "tv_snr_min": 6.0,             # dB
    "voice_dominance_min": 2.0,    # ratio
    "voice_dominance_max": 5.0,    # ratio
    "peak_max": -3.0,              # dBFS (clipping threshold)
    "music_energy_max_ratio": 0.25,  # music energy < 25% of voice
}


# ──────────────────────────────────────────────
# Recommendation engine
# ──────────────────────────────────────────────

def generate_recommendations(results: dict[str, Any]) -> list[dict[str, str]]:
    """Generate actionable recommendations based on phase results.

    Args:
        results: Dict with phase keys containing RMS, peak, SNR, etc.

    Returns:
        List of recommendation dicts with 'condition', 'severity', and 'action'.
    """
    recs = []
    p1 = results.get("phase1", {})
    p2 = results.get("phase2", {})
    p3 = results.get("phase3", {})
    p4 = results.get("phase4", {})
    p5 = results.get("phase5", {})

    noise_floor = p1.get("rms_dbfs", -96.0)

    # Phase 1: Noise floor assessment
    if noise_floor > -50.0:
        recs.append({
            "condition": f"Noise floor too high ({noise_floor:.1f} dBFS > -50 dBFS)",
            "severity": "warning",
            "action": "Reduce gain. Turn the **gain knob on the back of the Yeti** counter-clockwise.",
        })
    elif noise_floor > -55.0:
        recs.append({
            "condition": f"Noise floor marginal ({noise_floor:.1f} dBFS)",
            "severity": "info",
            "action": "Noise floor is borderline. Consider reducing gain slightly (back knob, CCW).",
        })
    elif noise_floor < -70.0:
        recs.append({
            "condition": f"Noise floor very low ({noise_floor:.1f} dBFS)",
            "severity": "info",
            "action": "Gain is conservative. You have headroom to increase gain (back knob, CW) for a stronger signal.",
        })
    else:
        recs.append({
            "condition": f"Noise floor good ({noise_floor:.1f} dBFS)",
            "severity": "pass",
            "action": "Noise floor is within target range.",
        })

    # Phase 2: Voice assessment
    if p2:
        voice_snr = p2.get("snr_db", 0.0)
        voice_peak = p2.get("peak_dbfs", -96.0)

        if voice_peak > -3.0:
            recs.append({
                "condition": f"Clipping risk! Voice peak at {voice_peak:.1f} dBFS",
                "severity": "danger",
                "action": "Reduce gain (back knob, CCW) or move back from the mic. Peaks should be below -3 dBFS.",
            })
        elif voice_peak > -6.0:
            recs.append({
                "condition": f"Voice peak high ({voice_peak:.1f} dBFS)",
                "severity": "info",
                "action": "Voice peaks are a bit hot. Monitor for clipping during loud speech.",
            })

        if voice_snr < 15.0:
            recs.append({
                "condition": f"Voice too quiet (SNR {voice_snr:.1f} dB < 15 dB)",
                "severity": "warning",
                "action": "Voice too quiet. Increase gain (back knob, CW) or move mic closer (6-10 inches).",
            })
        elif voice_snr < 20.0:
            recs.append({
                "condition": f"Voice SNR marginal ({voice_snr:.1f} dB)",
                "severity": "info",
                "action": "Voice SNR is borderline. Consider moving mic slightly closer or increasing gain.",
            })
        elif voice_snr > 40.0:
            recs.append({
                "condition": f"Excellent voice isolation (SNR {voice_snr:.1f} dB)",
                "severity": "pass",
                "action": "Excellent voice isolation.",
            })
        else:
            recs.append({
                "condition": f"Voice SNR good ({voice_snr:.1f} dB)",
                "severity": "pass",
                "action": "Voice signal-to-noise ratio is within target.",
            })

    # Phase 3: TV/speaker assessment
    if p3:
        tv_snr = p3.get("snr_db", 0.0)

        if tv_snr < 6.0:
            recs.append({
                "condition": f"TV barely audible (SNR {tv_snr:.1f} dB < 6 dB)",
                "severity": "warning",
                "action": "TV barely audible. Try switching to **Omnidirectional** pattern (back bottom knob) or increase TV volume.",
            })
        elif tv_snr > 25.0:
            recs.append({
                "condition": f"TV pickup very clear (SNR {tv_snr:.1f} dB)",
                "severity": "pass",
                "action": "TV pickup is clear. Cardioid pattern works well.",
            })
        else:
            recs.append({
                "condition": f"TV pickup adequate (SNR {tv_snr:.1f} dB)",
                "severity": "pass",
                "action": "TV/speaker audio is being captured adequately.",
            })

    # Phase 4: Voice dominance assessment
    if p4:
        dominance = p4.get("voice_dominance_ratio", 0.0)

        if dominance < 1.5:
            recs.append({
                "condition": f"Voice not dominant enough (ratio {dominance:.1f}x < 1.5x)",
                "severity": "warning",
                "action": "Voice not dominant enough. Move the mic closer to your mouth or increase gain.",
            })
        elif dominance > 10.0:
            recs.append({
                "condition": f"TV too quiet relative to voice (ratio {dominance:.1f}x > 10x)",
                "severity": "warning",
                "action": "TV is too quiet relative to voice. Try **Omnidirectional** pattern or increase TV volume.",
            })
        elif 2.0 <= dominance <= 5.0:
            recs.append({
                "condition": f"Good voice/TV balance (ratio {dominance:.1f}x)",
                "severity": "pass",
                "action": "Good balance between voice and TV audio.",
            })
        else:
            recs.append({
                "condition": f"Voice dominance ratio: {dominance:.1f}x",
                "severity": "info",
                "action": f"Voice dominance is {'slightly low' if dominance < 2.0 else 'slightly high'} but acceptable.",
            })

    # Phase 5: Music level assessment
    if p5:
        music_ratio = p5.get("music_energy_ratio", 0.0)
        if music_ratio > 0.25:
            recs.append({
                "condition": f"Music too prominent ({music_ratio:.0%} of voice energy)",
                "severity": "warning",
                "action": "Background music is too prominent. Use **Cardioid** pattern and position mic closer to mouth.",
            })

    return recs


def recommend_pattern(results: dict[str, Any]) -> dict[str, str]:
    """Recommend a pickup pattern based on calibration results.

    Returns:
        Dict with 'pattern' and 'reasoning' keys.
    """
    p3 = results.get("phase3", {})
    p4 = results.get("phase4", {})
    tv_snr = p3.get("snr_db", 0.0)
    dominance = p4.get("voice_dominance_ratio", 0.0)

    if tv_snr < 6.0:
        return {
            "pattern": "Omnidirectional",
            "reasoning": (
                f"TV speaker SNR is low ({tv_snr:.1f} dB). Omnidirectional pattern "
                "picks up sound equally from all directions, which will improve TV audio capture."
            ),
        }

    if dominance > 10.0:
        return {
            "pattern": "Omnidirectional",
            "reasoning": (
                f"Voice is too dominant ({dominance:.1f}x over TV). Omnidirectional pattern "
                "will balance the pickup between voice and room audio."
            ),
        }

    return {
        "pattern": "Cardioid",
        "reasoning": (
            "Cardioid provides the best voice isolation while still picking up "
            "sufficient TV/speaker audio. This is the recommended default."
        ),
    }


def recommend_positioning(results: dict[str, Any]) -> str:
    """Generate positioning recommendation based on results."""
    p2 = results.get("phase2", {})
    p3 = results.get("phase3", {})
    voice_snr = p2.get("snr_db", 0.0)
    voice_peak = p2.get("peak_dbfs", -96.0)

    lines = []

    if voice_peak > -3.0:
        lines.append("- Move back from the mic slightly (10-12 inches) to prevent clipping.")
    elif voice_snr < 15.0:
        lines.append("- Move mic closer to your mouth (6-8 inches) for a stronger voice signal.")
    elif voice_snr < 20.0:
        lines.append("- Position mic 6-10 inches from your mouth for optimal voice capture.")
    else:
        lines.append("- Current distance is good. Keep mic 8-12 inches from your mouth.")

    lines.append("- Angle the mic slightly toward your mouth (not straight on) to reduce plosives.")
    lines.append("- Keep the mic between you and the TV/speakers so it captures both sources.")
    lines.append("- Ensure the front of the mic (with the Blue logo) faces you.")

    return "\n".join(lines)


# ──────────────────────────────────────────────
# Success criteria check
# ──────────────────────────────────────────────

def check_success_criteria(results: dict[str, Any]) -> list[dict[str, Any]]:
    """Check all results against success criteria.

    Returns:
        List of criteria dicts with 'name', 'value', 'target', 'passed'.
    """
    criteria = []
    p1 = results.get("phase1", {})
    p2 = results.get("phase2", {})
    p3 = results.get("phase3", {})
    p4 = results.get("phase4", {})
    p5 = results.get("phase5", {})

    noise_floor = p1.get("rms_dbfs", -96.0)
    criteria.append({
        "name": "Noise floor",
        "value": f"{noise_floor:.1f} dBFS",
        "target": f"< {THRESHOLDS['noise_floor_max']} dBFS",
        "passed": noise_floor < THRESHOLDS["noise_floor_max"],
    })

    voice_snr = p2.get("snr_db", 0.0)
    criteria.append({
        "name": "Voice SNR",
        "value": f"{voice_snr:.1f} dB",
        "target": f"> {THRESHOLDS['voice_snr_min']} dB",
        "passed": voice_snr > THRESHOLDS["voice_snr_min"],
    })

    tv_snr = p3.get("snr_db", 0.0)
    criteria.append({
        "name": "TV speaker SNR",
        "value": f"{tv_snr:.1f} dB",
        "target": f"> {THRESHOLDS['tv_snr_min']} dB",
        "passed": tv_snr > THRESHOLDS["tv_snr_min"],
    })

    dominance = p4.get("voice_dominance_ratio", 0.0)
    in_range = THRESHOLDS["voice_dominance_min"] <= dominance <= THRESHOLDS["voice_dominance_max"]
    criteria.append({
        "name": "Voice dominance",
        "value": f"{dominance:.1f}x",
        "target": f"{THRESHOLDS['voice_dominance_min']}x - {THRESHOLDS['voice_dominance_max']}x",
        "passed": in_range,
    })

    voice_peak = p2.get("peak_dbfs", -96.0)
    criteria.append({
        "name": "No clipping",
        "value": f"{voice_peak:.1f} dBFS",
        "target": f"< {THRESHOLDS['peak_max']} dBFS",
        "passed": voice_peak < THRESHOLDS["peak_max"],
    })

    music_ratio = p5.get("music_energy_ratio", 0.0)
    criteria.append({
        "name": "Music level",
        "value": f"{music_ratio:.0%}",
        "target": f"< {THRESHOLDS['music_energy_max_ratio']:.0%} of voice energy",
        "passed": music_ratio < THRESHOLDS["music_energy_max_ratio"],
    })

    return criteria


# ──────────────────────────────────────────────
# Measurements table
# ──────────────────────────────────────────────

def generate_measurements_table(results: dict[str, Any]) -> str:
    """Generate a markdown measurements table from phase results."""
    phases = [
        ("Phase 1: Silence", "phase1"),
        ("Phase 2: Voice", "phase2"),
        ("Phase 3: TV Audio", "phase3"),
        ("Phase 4: Voice + TV", "phase4"),
        ("Phase 5: Full Mix", "phase5"),
    ]

    lines = [
        "| Phase | RMS (dBFS) | Peak (dBFS) | SNR (dB) | Dominant Band |",
        "|-------|-----------|-------------|----------|---------------|",
    ]

    for label, key in phases:
        p = results.get(key, {})
        if not p:
            lines.append(f"| {label} | — | — | — | — |")
            continue
        rms = p.get("rms_dbfs", None)
        peak = p.get("peak_dbfs", None)
        snr = p.get("snr_db", None)
        band = p.get("dominant_band", "—")
        rms_str = f"{rms:.1f}" if rms is not None else "—"
        peak_str = f"{peak:.1f}" if peak is not None else "—"
        snr_str = f"{snr:.1f}" if snr is not None else "—"
        lines.append(f"| {label} | {rms_str} | {peak_str} | {snr_str} | {band} |")

    return "\n".join(lines)


def generate_comparison_table(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
) -> str:
    """Generate a comparison table between current and previous run."""
    if previous is None:
        return generate_measurements_table(current)

    phases = [
        ("Phase 1: Silence", "phase1", "rms_dbfs"),
        ("Phase 2: Voice", "phase2", "snr_db"),
        ("Phase 3: TV Audio", "phase3", "snr_db"),
        ("Phase 4: Voice + TV", "phase4", "voice_dominance_ratio"),
    ]

    lines = [
        "| Phase | Metric | Previous | Current | Change |",
        "|-------|--------|----------|---------|--------|",
    ]

    for label, key, metric in phases:
        prev_val = previous.get(key, {}).get(metric)
        curr_val = current.get(key, {}).get(metric)
        if prev_val is not None and curr_val is not None:
            diff = curr_val - prev_val
            arrow = "improved" if _is_improvement(key, diff) else "regressed" if diff != 0 else "same"
            lines.append(
                f"| {label} | {metric} | {prev_val:.1f} | {curr_val:.1f} | {diff:+.1f} ({arrow}) |"
            )
        else:
            lines.append(f"| {label} | {metric} | — | — | — |")

    return "\n".join(lines)


def _is_improvement(phase_key: str, diff: float) -> bool:
    """Determine if a change is an improvement for the given phase."""
    # For noise floor, lower is better (negative diff = improvement)
    if phase_key == "phase1":
        return diff < 0
    # For SNR metrics, higher is better
    return diff > 0


# ──────────────────────────────────────────────
# Spectral plots
# ──────────────────────────────────────────────

def generate_spectral_plots(
    results: dict[str, Any],
    output_dir: str,
) -> list[str]:
    """Generate per-phase spectrum PNGs and an overlay comparison.

    Args:
        results: Phase results containing 'spectrum' data.
        output_dir: Directory to save PNGs.

    Returns:
        List of generated file paths.
    """
    os.makedirs(output_dir, exist_ok=True)
    generated = []

    phase_labels = {
        "phase1": "Phase 1: Silence Baseline",
        "phase2": "Phase 2: Voice Only",
        "phase3": "Phase 3: TV/Speaker Audio",
        "phase4": "Phase 4: Voice + TV",
        "phase5": "Phase 5: Full Mix",
    }

    # Individual phase plots
    for key, label in phase_labels.items():
        p = results.get(key, {})
        spectrum = p.get("spectrum")
        if spectrum is None:
            continue

        freqs, psd = spectrum["freqs"], spectrum["psd"]

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.semilogy(freqs, psd)
        ax.set_xlabel("Frequency (Hz)")
        ax.set_ylabel("Power Spectral Density")
        ax.set_title(label)
        ax.set_xlim(20, 20000)
        ax.axvspan(300, 3000, alpha=0.1, color="green", label="Speech band")
        ax.legend()
        ax.grid(True, alpha=0.3)

        path = os.path.join(output_dir, f"{key}_spectrum.png")
        fig.savefig(path, dpi=100, bbox_inches="tight")
        plt.close(fig)
        generated.append(path)

    # Overlay comparison
    fig, ax = plt.subplots(figsize=(12, 5))
    colors = ["#888888", "#2196F3", "#FF9800", "#4CAF50", "#9C27B0"]
    for (key, label), color in zip(phase_labels.items(), colors):
        p = results.get(key, {})
        spectrum = p.get("spectrum")
        if spectrum is None:
            continue
        ax.semilogy(spectrum["freqs"], spectrum["psd"], label=label, color=color, alpha=0.8)

    ax.set_xlabel("Frequency (Hz)")
    ax.set_ylabel("Power Spectral Density")
    ax.set_title("All Phases — Spectral Comparison")
    ax.set_xlim(20, 20000)
    ax.axvspan(300, 3000, alpha=0.1, color="green", label="Speech band")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

    path = os.path.join(output_dir, "all_phases_overlay.png")
    fig.savefig(path, dpi=100, bbox_inches="tight")
    plt.close(fig)
    generated.append(path)

    return generated


# ──────────────────────────────────────────────
# Markdown report
# ──────────────────────────────────────────────

def generate_report_markdown(
    results: dict[str, Any],
    run_number: int,
    previous_results: dict[str, Any] | None = None,
) -> str:
    """Generate a full markdown calibration report.

    Args:
        results: Phase results dict.
        run_number: Current run number.
        previous_results: Results from previous run for comparison.

    Returns:
        Markdown string.
    """
    lines = [
        f"# Blue Yeti Calibration Report — Run {run_number:03d}",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Measurements",
        "",
        generate_measurements_table(results),
        "",
    ]

    if previous_results:
        lines.extend([
            "## Comparison with Previous Run",
            "",
            generate_comparison_table(results, previous_results),
            "",
        ])

    # Success criteria
    criteria = check_success_criteria(results)
    all_passed = all(c["passed"] for c in criteria)

    lines.extend([
        "## Success Criteria",
        "",
        "| Criterion | Value | Target | Status |",
        "|-----------|-------|--------|--------|",
    ])
    for c in criteria:
        status = "PASS" if c["passed"] else "FAIL"
        lines.append(f"| {c['name']} | {c['value']} | {c['target']} | {status} |")

    lines.append("")

    if all_passed:
        lines.append("**All criteria met! Calibration complete.**")
    else:
        failed = [c["name"] for c in criteria if not c["passed"]]
        lines.append(f"**Failed criteria**: {', '.join(failed)}")

    # Recommendations
    recs = generate_recommendations(results)
    lines.extend([
        "",
        "## Recommendations",
        "",
    ])
    for rec in recs:
        icon = {"danger": "[!]", "warning": "[!]", "info": "[i]", "pass": "[+]"}.get(
            rec["severity"], "[-]"
        )
        lines.append(f"- {icon} **{rec['condition']}**: {rec['action']}")

    # Pattern recommendation
    pattern = recommend_pattern(results)
    lines.extend([
        "",
        "## Recommended Pattern",
        "",
        f"**{pattern['pattern']}** — {pattern['reasoning']}",
        "",
    ])

    # Positioning
    positioning = recommend_positioning(results)
    lines.extend([
        "## Positioning",
        "",
        positioning,
        "",
    ])

    # Spectral plots references
    lines.extend([
        "## Spectral Analysis",
        "",
        "See `plots/` directory for per-phase spectrum plots and overlay comparison.",
        "",
    ])

    return "\n".join(lines)


# ──────────────────────────────────────────────
# JSON persistence
# ──────────────────────────────────────────────

def _serialize_results(results: dict[str, Any]) -> dict[str, Any]:
    """Make results JSON-serializable by converting numpy arrays to lists."""
    serialized = {}
    for key, value in results.items():
        if isinstance(value, dict):
            inner = {}
            for k, v in value.items():
                if k == "spectrum":
                    # Convert numpy arrays in spectrum data
                    inner[k] = {
                        "freqs": v["freqs"].tolist() if hasattr(v["freqs"], "tolist") else v["freqs"],
                        "psd": v["psd"].tolist() if hasattr(v["psd"], "tolist") else v["psd"],
                    }
                elif hasattr(v, "tolist"):
                    inner[k] = v.tolist()
                else:
                    inner[k] = v
            serialized[key] = inner
        elif hasattr(value, "tolist"):
            serialized[key] = value.tolist()
        else:
            serialized[key] = value
    return serialized


def save_results_json(
    results: dict[str, Any],
    run_number: int,
    json_path: str = "yeti_calibration_results.json",
) -> None:
    """Append run results to the accumulated JSON results file."""
    if os.path.exists(json_path):
        with open(json_path) as f:
            all_results = json.load(f)
    else:
        all_results = {"runs": []}

    entry = {
        "run_number": run_number,
        "timestamp": datetime.now().isoformat(),
        "results": _serialize_results(results),
    }
    all_results["runs"].append(entry)

    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)


def save_final_config(
    results: dict[str, Any],
    device_index: int,
    recommended_gain: int = 35,
    recommended_pattern: str = "Cardioid",
    recommended_distance: int = 8,
) -> str:
    """Save final calibration config to ~/.config/audio_calibration.json.

    Returns:
        Path to the saved config file.
    """
    config_dir = os.path.expanduser("~/.config")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "audio_calibration.json")

    p1 = results.get("phase1", {})
    p2 = results.get("phase2", {})

    config = {
        "preferred_input_device": "Blue Yeti",
        "device_index": device_index,
        "sample_rate": 48000,
        "channels": 1,
        "recommended_gain_percent": recommended_gain,
        "recommended_pattern": recommended_pattern,
        "recommended_distance_inches": recommended_distance,
        "noise_floor_dbfs": round(p1.get("rms_dbfs", -60.0), 1),
        "voice_snr_db": round(p2.get("snr_db", 0.0), 1),
        "calibrated_at": datetime.now().isoformat(),
    }

    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    return config_path
