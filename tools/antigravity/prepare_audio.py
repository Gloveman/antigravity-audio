#!/usr/bin/env python3
"""Prepare arbitrary local audio files for the mixing/mastering pipeline.

Converts any common audio format (MP3/WAV/FLAC/M4A/WEBM/OGG) to 44.1 kHz
stereo 16-bit PCM WAV, optionally trims dead trailing silence, repairs digital
clipping via FFmpeg AR de-clip (`adeclip`), and optionally separates stems
using local Demucs into `<output_dir>/stems/<track_name>/*.wav` so
`tools/mixing/mix_tracks.py` can process non-Suno audio directly.
"""
from __future__ import annotations

import argparse
import array
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".webm", ".ogg", ".aac", ".opus"}


def configure_stdio() -> None:
    """Ensure UTF-8 output on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError(
            "ffmpeg and ffprobe must be installed and available on PATH."
        )


def run_cmd(cmd: list[str], capture: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=True,
        capture_output=capture,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def inspect_wav_clipping(wav_path: Path, threshold: float = 0.985) -> tuple[float, float]:
    """Return (peak_ratio, clipped_pct) using stdlib wave + array (16-bit/32-bit fallback via ffmpeg)."""
    with wave.open(str(wav_path), "rb") as w:
        sampwidth = w.getsampwidth()
        nframes = w.getnframes()
        if sampwidth != 2 or nframes == 0:
            # Measure via ffmpeg astats if not 16-bit PCM
            return _inspect_via_ffprobe_astats(wav_path)
        raw = w.readframes(nframes)

    samples = array.array("h")
    samples.frombytes(raw)
    if sys.byteorder != "little":
        samples.byteswap()
    if not samples:
        return 0.0, 0.0

    thresh_int = int(32768.0 * threshold)
    peak_int = 0
    clipped = 0
    for val in samples:
        av = -val if val < 0 else val
        if av > peak_int:
            peak_int = av
        if av >= thresh_int:
            clipped += 1
    return peak_int / 32768.0, 100.0 * clipped / len(samples)


def _inspect_via_ffprobe_astats(wav_path: Path) -> tuple[float, float]:
    res = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-nostats", "-i", str(wav_path),
            "-af", "astats=metadata=1:reset=0", "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    peak = 0.0
    for line in res.stderr.splitlines():
        if "Peak level dB:" in line:
            try:
                db = float(line.split("Peak level dB:")[-1].strip())
                peak = 10.0 ** (db / 20.0)
            except ValueError:
                pass
    return peak, 0.0


def detect_active_end_sec(wav_path: Path, threshold_db: float = -60.0) -> float | None:
    """Detect trailing silence >= 2.0s below threshold_db and return safe trim end seconds."""
    res = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-i", str(wav_path),
            "-af", f"silencedetect=noise={threshold_db}dB:d=2.0",
            "-f", "null", "-",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    # Get total duration
    probe = run_cmd(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(wav_path),
        ],
        capture=True,
    )
    duration = float(json.loads(probe.stdout)["format"]["duration"])

    last_silence_start: float | None = None
    has_silence_end_after = False
    for line in res.stderr.splitlines():
        if "silence_start:" in line:
            try:
                last_silence_start = float(line.split("silence_start:")[-1].strip().split()[0])
                has_silence_end_after = False
            except ValueError:
                pass
        elif "silence_end:" in line:
            has_silence_end_after = True

    if (
        last_silence_start is not None
        and not has_silence_end_after
        and duration - last_silence_start >= 2.0
        and last_silence_start > 5.0
    ):
        return min(duration, last_silence_start + 1.5)
    return None


def convert_to_raw_wav(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_cmd(
        [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le",
            str(dst),
        ]
    )


def prepare_one(
    src: Path,
    raw_dir: Path,
    declipped_dir: Path,
    stems_root: Path,
    declip_mode: str,
    headroom_db: float,
    trim_tail: bool,
    run_stems: bool,
    demucs_model: str,
    device: str,
    demucs_tmp: Path,
) -> dict[str, object]:
    track_name = src.stem
    raw_wav = raw_dir / f"{track_name}.wav"
    declipped_wav = declipped_dir / f"{track_name}.wav"

    convert_to_raw_wav(src, raw_wav)
    peak, clip_pct = inspect_wav_clipping(raw_wav)

    filters: list[str] = []
    trim_end = detect_active_end_sec(raw_wav) if trim_tail else None
    if trim_end is not None:
        fade_start = max(0.0, trim_end - 1.5)
        filters.append(f"afade=t=out:st={fade_start:.3f}:d=1.5")

    should_declip = declip_mode == "always" or (declip_mode == "auto" and peak >= 0.985)
    if should_declip:
        filters.append(f"volume={headroom_db:.2f}dB")
        filters.append("adeclip=w=55:o=75:a=8:t=10:n=1000:m=a")

    declipped_dir.mkdir(parents=True, exist_ok=True)
    if filters or trim_end is not None:
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(raw_wav),
        ]
        if trim_end is not None:
            cmd.extend(["-to", f"{trim_end:.3f}"])
        if filters:
            cmd.extend(["-af", ",".join(filters)])
        cmd.extend(["-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(declipped_wav)])
        run_cmd(cmd)
    else:
        shutil.copy2(raw_wav, declipped_wav)

    post_peak, post_clip_pct = inspect_wav_clipping(declipped_wav)

    stem_files: list[str] = []
    if run_stems:
        demucs_tmp.mkdir(parents=True, exist_ok=True)
        run_cmd(
            [
                sys.executable, "-m", "demucs",
                "-n", demucs_model,
                "-d", device,
                "-o", str(demucs_tmp),
                str(declipped_wav),
            ]
        )
        produced_dir = demucs_tmp / demucs_model / declipped_wav.stem
        if not produced_dir.is_dir():
            raise RuntimeError(f"Expected Demucs stem folder not found: {produced_dir}")
        track_stems_dir = stems_root / track_name
        track_stems_dir.mkdir(parents=True, exist_ok=True)
        for wav in sorted(produced_dir.glob("*.wav")):
            dest = track_stems_dir / wav.name
            shutil.copy2(wav, dest)
            stem_files.append(wav.name)

    return {
        "track": track_name,
        "pre_peak": round(peak, 4),
        "pre_clip_pct": round(clip_pct, 4),
        "declipped": should_declip,
        "trimmed_end_sec": round(trim_end, 2) if trim_end is not None else None,
        "post_peak": round(post_peak, 4),
        "post_clip_pct": round(post_clip_pct, 4),
        "stems": stem_files,
    }


def collect_inputs(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        files = [
            p for p in sorted(input_path.iterdir())
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
        ]
        if not files:
            raise FileNotFoundError(f"No supported audio files found in {input_path}")
        return files
    raise FileNotFoundError(f"Input path does not exist: {input_path}")


def main() -> int:
    configure_stdio()
    parser = argparse.ArgumentParser(
        description="Prepare local audio files (normalize WAV, optional tail trim, adeclip, Demucs stems)."
    )
    parser.add_argument("input", help="Path to an audio file or directory of audio files.")
    parser.add_argument(
        "-o", "--output-dir",
        default="./work_audio",
        help="Working directory for raw/, declipped/, and stems/ (default: ./work_audio).",
    )
    parser.add_argument(
        "--declip",
        choices=["auto", "always", "never"],
        default="auto",
        help="When to apply FFmpeg adeclip (default: auto when peak >= 0.985).",
    )
    parser.add_argument(
        "--headroom-db",
        type=float,
        default=-3.0,
        help="Pre-declip headroom in dB (default: -3.0).",
    )
    parser.add_argument(
        "--trim-tail",
        action="store_true",
        help="Trim trailing dead silence (>=2s below -60 dBFS) with a 1.5s fade-out.",
    )
    parser.add_argument(
        "--stems",
        action="store_true",
        help="Run local Demucs separation and populate <output-dir>/stems/<track>/.",
    )
    parser.add_argument(
        "--demucs-model",
        default="htdemucs",
        help="Demucs model name, e.g. htdemucs or htdemucs_6s (default: htdemucs).",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Demucs compute device (default: cpu).",
    )
    args = parser.parse_args()

    require_ffmpeg()
    input_path = Path(args.input).expanduser().resolve()
    out_dir = Path(args.output_dir).expanduser().resolve()
    files = collect_inputs(input_path)

    raw_dir = out_dir / "raw"
    declipped_dir = out_dir / "declipped"
    stems_root = out_dir / "stems"
    demucs_tmp = out_dir / "_demucs_tmp"

    print(f"Preparing {len(files)} file(s) -> {out_dir}")
    for f in files:
        res = prepare_one(
            src=f,
            raw_dir=raw_dir,
            declipped_dir=declipped_dir,
            stems_root=stems_root,
            declip_mode=args.declip,
            headroom_db=args.headroom_db,
            trim_tail=args.trim_tail,
            run_stems=args.stems,
            demucs_model=args.demucs_model,
            device=args.device,
            demucs_tmp=demucs_tmp,
        )
        trim_note = f", trimmed@{res['trimmed_end_sec']}s" if res["trimmed_end_sec"] else ""
        stem_note = f", stems={len(res['stems'])}" if res["stems"] else ""
        print(
            f"  [OK] {res['track']}: peak {res['pre_peak']} -> {res['post_peak']}, "
            f"declip={res['declipped']}{trim_note}{stem_note}"
        )

    print("\nNext steps:")
    print(f"  QC/Analyze: python tools/antigravity/audio_cli.py qc \"{declipped_dir}\"")
    if args.stems:
        print(f"  Mix stems:  python tools/antigravity/audio_cli.py mix \"{out_dir}\" --genre <genre>")
    else:
        print(f"  Full-mix:   python tools/antigravity/audio_cli.py mix \"{declipped_dir}\" --full-mix --genre <genre>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
