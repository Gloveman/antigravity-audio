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


def _missing_dep_error(exc: ModuleNotFoundError) -> int:
    print(
        f"[ERROR] Missing dependency '{exc.name}'. Install with:\n"
        f"  pip install -r \"{REPO_ROOT / 'requirements-audio.txt'}\"",
        file=sys.stderr,
    )
    return 1


def _run_adm_check(extra_args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="audio_cli.py adm-check",
        description="Check AAC/M4A inter-sample clipping against a true-peak ceiling (ADM check).",
    )
    parser.add_argument("path", help="WAV file or directory of WAV files to validate.")
    parser.add_argument("-b", "--bitrate", type=int, default=256, help="AAC bitrate in kbps (default: 256).")
    parser.add_argument("--ceiling", type=float, default=-1.0, help="True-peak ceiling in dBTP (default: -1.0).")
    parser.add_argument(
        "--encoder",
        choices=["aac", "afconvert", "libfdk_aac"],
        default="aac",
        help="AAC encoder backend (default: aac).",
    )
    args = parser.parse_args(extra_args)

    try:
        from tools.mastering.adm_validation import ADMValidationError, check_aac_intersample_clips
    except ModuleNotFoundError as exc:
        return _missing_dep_error(exc)

    target = Path(args.path).expanduser().resolve()
    wavs = [target] if target.is_file() else sorted(target.glob("*.wav"))
    if not wavs:
        print(f"[ERROR] No WAV files found at: {target}", file=sys.stderr)
        return 1

    any_fail = False
    print(f"{'Track':<32} {'Encoder':>9} {'Peak dBFS':>10} {'Ceiling':>8} {'Clips':>7} {'Status'}")
    print("-" * 80)
    for wav in wavs:
        try:
            r = check_aac_intersample_clips(
                wav,
                encoder=args.encoder,
                ceiling_db=args.ceiling,
                bitrate_kbps=args.bitrate,
            )
        except ADMValidationError as exc:
            print(f"{wav.name[:31]:<32} {'error':>9} {'n/a':>10} {args.ceiling:>8.1f} {'n/a':>7} ERROR ({exc})")
            any_fail = True
            continue
        status = "FAIL" if r["clips_found"] else "PASS"
        if r["clips_found"]:
            any_fail = True
        print(
            f"{r['filename'][:31]:<32} {r['encoder_used']:>9} "
            f"{r['peak_db_decoded']:>10.2f} {r['ceiling_db']:>8.1f} {r['clip_count']:>7} {status}"
        )
    return 1 if any_fail else 0


def _run_excite(extra_args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="audio_cli.py excite",
        description="Add synthetic upper harmonics via saturate-hipass-diff-mix to brighten dark stems.",
    )
    parser.add_argument("input_wav", help="Source WAV file (typically a dark or muffled stem).")
    parser.add_argument("-o", "--output", help="Output WAV path (default: <input>_excited.wav).")
    parser.add_argument("--amount-db", type=float, default=2.0, help="Excitation level in dB (default: 2.0).")
    parser.add_argument("--low-hz", type=float, default=600.0, help="High-pass cutoff for added harmonics in Hz (default: 600).")
    parser.add_argument("--high-hz", type=float, default=12000.0, help="Upper band boundary in Hz (default: 12000).")
    parser.add_argument("--drive", type=float, default=20.0, help="tanh saturation drive (default: 20.0).")
    args = parser.parse_args(extra_args)

    try:
        import numpy as np
        import soundfile as sf
        from tools.mixing.excitation import apply_harmonic_excitation
    except ModuleNotFoundError as exc:
        return _missing_dep_error(exc)

    src = Path(args.input_wav).expanduser().resolve()
    if not src.is_file():
        print(f"[ERROR] Input WAV not found: {src}", file=sys.stderr)
        return 1

    out = Path(args.output).expanduser().resolve() if args.output else src.with_name(f"{src.stem}_excited.wav")
    out.parent.mkdir(parents=True, exist_ok=True)

    info = sf.info(str(src))
    data, rate = sf.read(str(src), dtype="float64")
    pre_peak = float(np.max(np.abs(data)))
    pre_rms = float(np.sqrt(np.mean(data ** 2)))

    excited = apply_harmonic_excitation(
        data,
        rate,
        amount_db=args.amount_db,
        freq_range=(args.low_hz, args.high_hz),
        drive=args.drive,
    )
    post_peak = float(np.max(np.abs(excited)))
    if post_peak > 0.985:
        excited = excited * (0.985 / post_peak)
        post_peak = float(np.max(np.abs(excited)))
    post_rms = float(np.sqrt(np.mean(excited ** 2)))

    subtype = info.subtype if info.subtype in {"PCM_16", "PCM_24", "PCM_32", "FLOAT", "DOUBLE"} else "PCM_24"
    sf.write(str(out), excited, rate, subtype=subtype)

    def _db(x: float) -> str:
        return f"{20.0 * np.log10(x):+.2f} dBFS" if x > 0 else "-inf dBFS"

    print(
        f"[OK] Excited ({args.amount_db:+.1f} dB, {args.low_hz:.0f}-{args.high_hz:.0f} Hz, drive={args.drive}): {out}\n"
        f"     Peak: {_db(pre_peak)} -> {_db(post_peak)} | RMS: {_db(pre_rms)} -> {_db(post_rms)}"
    )
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

    subcommands = [*SCRIPT_TARGETS.keys(), "mono-check", "codec-preview", "adm-check", "excite"]
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
    if parsed.subcommand == "adm-check":
        return _run_adm_check(parsed.args)
    if parsed.subcommand == "excite":
        return _run_excite(parsed.args)
    return _run_forwarded_script(parsed.subcommand, parsed.args)


if __name__ == "__main__":
    raise SystemExit(main())
