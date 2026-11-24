#!/usr/bin/env python3
"""Unified Antigravity audio processing CLI dispatcher.

Routes standalone audio subcommands to `tools/antigravity/prepare_audio.py`,
`tools/mixing/mix_tracks.py`, and `tools/mastering/*.py` with UTF-8 stdio
and clean dependency error hints. Uses Python stdlib only at top level so
`--help` always works even before `requirements-audio.txt` is installed.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SCRIPT_TARGETS: dict[str, Path] = {
    "prepare": REPO_ROOT / "tools" / "antigravity" / "prepare_audio.py",
    "qc": REPO_ROOT / "tools" / "mastering" / "qc_tracks.py",
    "analyze": REPO_ROOT / "tools" / "mastering" / "analyze_tracks.py",
    "mix": REPO_ROOT / "tools" / "mixing" / "mix_tracks.py",
    "master": REPO_ROOT / "tools" / "mastering" / "master_tracks.py",
    "ref-master": REPO_ROOT / "tools" / "mastering" / "reference_master.py",
    "fix-dynamics": REPO_ROOT / "tools" / "mastering" / "fix_dynamic_track.py",
}


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _run_mono_check(extra_args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="audio_cli.py mono-check",
        description="Measure stereo-to-mono fold-down phase/energy deltas.",
    )
    parser.add_argument("path", help="WAV file or directory of WAV files to check.")
    args = parser.parse_args(extra_args)

    try:
        import soundfile as sf
        from tools.mastering.mono_fold import mono_fold_metrics
    except ModuleNotFoundError as exc:
        print(
            f"[ERROR] Missing dependency '{exc.name}'. Install with:\n"
            f"  pip install -r \"{REPO_ROOT / 'requirements-audio.txt'}\"",
            file=sys.stderr,
        )
        return 1

    target = Path(args.path).expanduser().resolve()
    wavs = [target] if target.is_file() else sorted(target.glob("*.wav"))
    if not wavs:
        print(f"[ERROR] No WAV files found at: {target}", file=sys.stderr)
        return 1

    any_fail = False
    print(f"{'Track':<32} {'Verdict':>7} {'Corr':>6} {'LUFS d':>7} {'Voc d':>7} {'Worst Band'}")
    print("-" * 80)
    for wav in wavs:
        data, rate = sf.read(str(wav))
        m = mono_fold_metrics(data, rate)
        lufs_d = m["lufs"]["delta_db"]
        voc_d = m["vocal_rms"]["delta_db"]
        worst = m["worst_band"]
        lufs_s = f"{lufs_d:+.1f}" if lufs_d is not None else "n/a"
        voc_s = f"{voc_d:+.1f}" if voc_d is not None else "n/a"
        worst_s = f"{worst['name']} ({worst['delta_db']:+.1f} dB)" if worst["name"] else "none"
        print(
            f"{wav.name[:31]:<32} {m['verdict']:>7} {m['stereo_correlation']:>6.2f} "
            f"{lufs_s:>7} {voc_s:>7} {worst_s}"
        )
        if m["verdict"] == "FAIL":
            any_fail = True
    return 1 if any_fail else 0


def _run_codec_preview(extra_args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="audio_cli.py codec-preview",
        description="Render a lossy AAC/M4A preview to audition codec compression artifacts.",
    )
    parser.add_argument("input_wav", help="Source mastered WAV file.")
    parser.add_argument("-o", "--output", help="Destination .m4a path (default: <input>.aac.m4a).")
    parser.add_argument("-b", "--bitrate", type=int, default=128, help="AAC bitrate in kbps (default: 128).")
    args = parser.parse_args(extra_args)

    sys.path.insert(0, str(REPO_ROOT))
    from tools.mastering.codec_preview import CodecPreviewError, render_aac_preview

    src = Path(args.input_wav).expanduser().resolve()
    out = Path(args.output).expanduser().resolve() if args.output else src.with_suffix(".aac.m4a")
    try:
        res = render_aac_preview(src, out, bitrate_kbps=args.bitrate)
    except CodecPreviewError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    print(f"[OK] Rendered {res['bitrate_kbps']} kbps preview: {res['output_path']} ({res['output_bytes']} bytes)")
    return 0


def _run_forwarded_script(subcmd: str, extra_args: list[str]) -> int:
    script = SCRIPT_TARGETS[subcmd]
    if not script.is_file():
        print(f"[ERROR] Target script not found: {script}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{REPO_ROOT}{os.pathsep}{existing_pp}" if existing_pp else str(REPO_ROOT)

    proc = subprocess.run(
        [sys.executable, str(script), *extra_args],
        env=env,
        capture_output=False,
        text=True,
    )
    if proc.returncode != 0:
        # Probe quick import check if a non-zero exit might be caused by missing audio packages
        probe = subprocess.run(
            [sys.executable, "-c", "import soundfile, pyloudnorm, scipy, numpy, yaml"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if probe.returncode != 0 and "ModuleNotFoundError" in probe.stderr:
            print(
                "\n[HINT] One or more audio dependencies are missing. Install them via:\n"
                f"  pip install -r \"{REPO_ROOT / 'requirements-audio.txt'}\"",
                file=sys.stderr,
            )
    return proc.returncode


def main() -> int:
    configure_stdio()
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    subcommands = [*SCRIPT_TARGETS.keys(), "mono-check", "codec-preview"]
    parser = argparse.ArgumentParser(
        description="Unified Antigravity CLI for standalone audio QC, preparation, mixing, and mastering.",
        epilog="Run `python tools/antigravity/audio_cli.py <subcommand> --help` for subcommand options.",
    )
    parser.add_argument(
        "subcommand",
        choices=subcommands,
        help="Audio tool subcommand to execute.",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded directly to the underlying tool.",
    )
    parsed = parser.parse_args()

    if parsed.subcommand == "mono-check":
        return _run_mono_check(parsed.args)
    if parsed.subcommand == "codec-preview":
        return _run_codec_preview(parsed.args)
    return _run_forwarded_script(parsed.subcommand, parsed.args)


if __name__ == "__main__":
    raise SystemExit(main())
