#!/usr/bin/env python3
"""Distortion-resistant Rubber Band pitch & tempo shifting for audio and video.

Uses FFmpeg's built-in `rubberband` filter with `pitchq=quality`,
`channels=together`, pre-shift headroom attenuation (-3.0 dB default), and a
transparent safety ceiling limiter (-1.0 dBFS default) to prevent phasiness,
transient smearing, and inter-sample clipping.

Supports both audio files (.wav, .mp3, .flac, .m4a, .ogg, .opus) and video
files (.mp4, .mkv, .mov, .webm) with synchronized A/V tempo scaling (`libx264`).
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys


@dataclass(frozen=True)
class PitchTempoMode:
    name: str
    description: str
    formant: str
    transients: str
    detector: str
    phase: str
    window: str
    smoothing: str
    pitchq: str = "quality"
    channels: str = "together"


MODES: dict[str, PitchTempoMode] = {
    "vocal": PitchTempoMode(
        name="vocal",
        description="Singing / full songs with vocals: preserves vocal formants to avoid chipmunk/giant voice timbre.",
        formant="preserved",
        transients="mixed",
        detector="compound",
        phase="laminar",
        window="standard",
        smoothing="off",
    ),
    "instrumental": PitchTempoMode(
        name="instrumental",
        description="Whistle, synth, acoustic, or instrumental melodies: crisp transients without formant filter ringing.",
        formant="shifted",
        transients="crisp",
        detector="compound",
        phase="laminar",
        window="standard",
        smoothing="off",
    ),
    "drums": PitchTempoMode(
        name="drums",
        description="Percussive drums/beats: short window and percussive detector to minimize kick/snare pre-echo.",
        formant="shifted",
        transients="crisp",
        detector="percussive",
        phase="laminar",
        window="short",
        smoothing="off",
    ),
    "smooth": PitchTempoMode(
        name="smooth",
        description="Ambient pads, strings, or sustained ballads: long window and smoothing for lush continuity.",
        formant="preserved",
        transients="smooth",
        detector="soft",
        phase="laminar",
        window="long",
        smoothing="on",
    ),
}

STANDARD_SAMPLE_RATES = {44100, 48000, 88200, 96000, 176400, 192000}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mov", ".webm"}
AUDIO_CODECS = {
    ".wav": ("pcm_s24le", []),
    ".mp3": ("libmp3lame", ["-b:a", "320k"]),
    ".m4a": ("aac", ["-b:a", "256k"]),
    ".aac": ("aac", ["-b:a", "256k"]),
    ".flac": ("flac", []),
    ".ogg": ("libvorbis", ["-q:a", "7"]),
    ".opus": ("libopus", ["-b:a", "192k"]),
}


def _normalize_wav_header(output_path: Path) -> None:
    """Rewrite FFmpeg WAVEX (WAVE_FORMAT_EXTENSIBLE) header to standard RIFF WAV when soundfile is available."""
    if output_path.suffix.lower() != ".wav":
        return
    try:
        import soundfile as sf
    except ModuleNotFoundError:
        return

    info = sf.info(str(output_path))
    if info.format == "WAVEX":
        data, sr = sf.read(str(output_path), dtype="float64")
        sf.write(str(output_path), data, sr, format="WAV", subtype="PCM_24")


def configure_stdio() -> None:
    """Ensure UTF-8 output on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def require_ffmpeg_rubberband() -> None:
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise RuntimeError("ffmpeg and ffprobe must be installed and available on PATH.")

    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    if "rubberband" not in res.stdout:
        raise RuntimeError(
            "FFmpeg was found, but the `rubberband` filter is not compiled in."
        )


def probe_media(input_path: Path) -> dict[str, object]:
    """Probe audio/video streams and sample rate using ffprobe."""
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-of",
            "json",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    info = json.loads(res.stdout or "{}")
    streams = info.get("streams", [])

    has_audio = False
    has_video = False
    sample_rate = 44100

    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "audio" and not has_audio:
            has_audio = True
            sr_raw = stream.get("sample_rate")
            if sr_raw:
                try:
                    sample_rate = int(sr_raw)
                except ValueError:
                    pass
        elif codec_type == "video":
            disp = stream.get("disposition") or {}
            if disp.get("attached_pic", 0) != 1:
                has_video = True

    if not has_audio:
        raise RuntimeError(f"No audio stream found in: {input_path}")

    return {
        "has_audio": has_audio,
        "has_video": has_video,
        "sample_rate": sample_rate,
    }


def build_audio_filter(
    mode: PitchTempoMode,
    total_semitones: float,
    speed: float,
    formant: str,
    transients: str,
    window: str,
    channels: str,
    headroom_db: float,
    ceiling_db: float,
    use_limiter: bool,
) -> str:
    """Build FFmpeg audio filter graph: headroom -> rubberband -> safety ceiling."""
    pitch_scale = 2.0 ** (total_semitones / 12.0)
    chain: list[str] = []

    if headroom_db < 0.0:
        chain.append(f"volume={headroom_db:g}dB")

    chain.append(
        f"rubberband=tempo={speed:.8f}:pitch={pitch_scale:.8f}:"
        f"transients={transients}:detector={mode.detector}:phase={mode.phase}:"
        f"window={window}:smoothing={mode.smoothing}:formant={formant}:"
        f"pitchq={mode.pitchq}:channels={channels}"
    )

    if use_limiter:
        lin_ceiling = 10.0 ** (ceiling_db / 20.0)
        chain.append(
            f"alimiter=limit={lin_ceiling:.6f}:attack=5:release=50:level=disabled"
        )

    return ",".join(chain)


def resolve_output_path(
    input_path: Path,
    output_arg: str | None,
    has_video: bool,
    audio_only: bool,
    total_semitones: float,
    speed: float,
) -> Path:
    if output_arg:
        return Path(output_arg).expanduser().resolve()

    default_ext = ".mp4" if (has_video and not audio_only) else ".wav"
    semi_tag = f"{total_semitones:+g}" if total_semitones != 0 else "0"
    speed_tag = f"{speed:g}x"
    return input_path.with_name(f"{input_path.stem}_p{semi_tag}_s{speed_tag}{default_ext}")


def build_ffmpeg_command(
    input_path: Path,
    output_path: Path,
    audio_filter: str,
    has_video: bool,
    audio_only: bool,
    speed: float,
    sample_rate: int,
    crf: int,
) -> tuple[list[str], bool]:
    """Assemble the FFmpeg command and return (cmd, is_video_output)."""
    out_ext = output_path.suffix.lower()
    is_video_output = has_video and (not audio_only) and (out_ext in VIDEO_EXTENSIONS)

    cmd: list[str] = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(input_path)]

    if is_video_output:
        cmd.extend(["-map", "0:v:0", "-map", "0:a:0"])
        if abs(speed - 1.0) < 1e-6:
            cmd.extend(["-c:v", "copy"])
        else:
            cmd.extend([
                "-vf", f"setpts=PTS/{speed:.8f}",
                "-c:v", "libx264",
                "-crf", str(crf),
                "-preset", "medium",
                "-pix_fmt", "yuv420p",
            ])
        cmd.extend(["-af", audio_filter, "-c:a", "aac", "-b:a", "256k", "-ar", str(sample_rate)])
        if out_ext == ".mp4":
            cmd.extend(["-movflags", "+faststart"])
    else:
        codec, extra_flags = AUDIO_CODECS.get(out_ext, ("pcm_s24le", []))
        cmd.extend(["-map", "0:a:0", "-vn", "-af", audio_filter, "-c:a", codec, *extra_flags])
        if out_ext == ".wav" or codec == "pcm_s24le":
            cmd.extend(["-ar", str(sample_rate)])

    cmd.append(str(output_path))
    return cmd, is_video_output


def print_modes() -> None:
    print("Available Rubber Band pitch-tempo modes:\n")
    for name, m in MODES.items():
        print(f"  {name}")
        print(f"    Description : {m.description}")
        print(
            f"    DSP options : formant={m.formant}, transients={m.transients}, "
            f"detector={m.detector}, phase={m.phase}, window={m.window}, "
            f"smoothing={m.smoothing}, pitchq={m.pitchq}, channels={m.channels}\n"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pitch_tempo.py",
        description="Distortion-resistant Rubber Band pitch & tempo shifter for audio and video.",
    )
    parser.add_argument("input_path", nargs="?", help="Source audio or video file.")
    parser.add_argument("-o", "--output", help="Output file path (default: <stem>_p<semi>_s<speed>x.<ext>).")
    parser.add_argument("--semitones", type=float, default=0.0, help="Pitch shift in semitones (e.g. +2, -1.5; default: 0).")
    parser.add_argument("--cents", type=float, default=0.0, help="Fine pitch offset in cents (-100..+100; default: 0).")
    parser.add_argument("--speed", type=float, default=1.0, help="Playback tempo multiplier (e.g. 1.1 for +10%%; default: 1.0).")
    parser.add_argument(
        "-m", "--mode",
        choices=list(MODES.keys()),
        default="vocal",
        help="Rubber Band DSP preset (default: vocal).",
    )
    parser.add_argument("--list-modes", action="store_true", help="List available DSP modes and exit.")

    parser.add_argument("--formant", choices=["preserved", "shifted"], default=None, help="Override formant handling.")
    parser.add_argument("--transients", choices=["crisp", "mixed", "smooth"], default=None, help="Override transient mode.")
    parser.add_argument("--window", choices=["standard", "short", "long"], default=None, help="Override analysis window.")
    parser.add_argument("--channels", choices=["together", "apart"], default=None, help="Override stereo channel linking.")

    parser.add_argument("--headroom-db", type=float, default=-3.0, help="Pre-shift attenuation in dB (default: -3.0).")
    parser.add_argument("--ceiling-db", type=float, default=-1.0, help="Safety alimiter ceiling in dBFS (default: -1.0).")
    parser.add_argument("--no-limiter", action="store_true", help="Disable post-shift safety ceiling limiter.")
    parser.add_argument("--sample-rate", type=int, default=None, help="Output sample rate in Hz (default: preserve source).")
    parser.add_argument("--audio-only", action="store_true", help="Extract audio only even when input is a video.")
    parser.add_argument("--crf", type=int, default=18, help="libx264 CRF when re-encoding video speed (default: 18).")
    parser.add_argument("--dry-run", action="store_true", help="Print planned FFmpeg filter graph and command without running.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = parse_args(argv)

    if args.list_modes:
        print_modes()
        return 0

    if not args.input_path:
        print("[ERROR] input_path is required unless --list-modes is set.", file=sys.stderr)
        return 2

    total_semitones = args.semitones + (args.cents / 100.0)
    if args.speed <= 0.0 or not (0.25 <= args.speed <= 4.0):
        print("[ERROR] --speed must be between 0.25 and 4.0.", file=sys.stderr)
        return 2
    if args.headroom_db > 0.0:
        print("[ERROR] --headroom-db must be <= 0.0.", file=sys.stderr)
        return 2
    if args.ceiling_db > 0.0:
        print("[ERROR] --ceiling-db must be <= 0.0.", file=sys.stderr)
        return 2
    if args.sample_rate is not None and args.sample_rate <= 0:
        print("[ERROR] --sample-rate must be > 0.", file=sys.stderr)
        return 2
    if abs(total_semitones) < 1e-6 and abs(args.speed - 1.0) < 1e-6:
        print("[ERROR] Nothing to shift: specify non-zero --semitones/--cents or --speed != 1.0.", file=sys.stderr)
        return 2

    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.is_file():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        return 1

    try:
        require_ffmpeg_rubberband()
        media_info = probe_media(input_path)
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    has_video = bool(media_info["has_video"])
    source_sr = int(media_info["sample_rate"])
    sr_note: str | None = None
    if args.sample_rate is not None:
        target_sr = args.sample_rate
    elif source_sr in STANDARD_SAMPLE_RATES:
        target_sr = source_sr
    else:
        target_sr = 44100
        sr_note = (
            f"[INFO] Non-standard source sample rate ({source_sr} Hz) normalized to 44100 Hz "
            "(override with --sample-rate)."
        )

    mode = MODES[args.mode]
    formant = args.formant or mode.formant
    transients = args.transients or mode.transients
    window = args.window or mode.window
    channels = args.channels or mode.channels

    audio_filter = build_audio_filter(
        mode=mode,
        total_semitones=total_semitones,
        speed=args.speed,
        formant=formant,
        transients=transients,
        window=window,
        channels=channels,
        headroom_db=args.headroom_db,
        ceiling_db=args.ceiling_db,
        use_limiter=not args.no_limiter,
    )
    output_path = resolve_output_path(
        input_path=input_path,
        output_arg=args.output,
        has_video=has_video,
        audio_only=args.audio_only,
        total_semitones=total_semitones,
        speed=args.speed,
    )
    cmd, is_video_output = build_ffmpeg_command(
        input_path=input_path,
        output_path=output_path,
        audio_filter=audio_filter,
        has_video=has_video,
        audio_only=args.audio_only,
        speed=args.speed,
        sample_rate=target_sr,
        crf=args.crf,
    )

    print(
        f"[pitch-tempo] Input: {input_path.name} | Mode: {mode.name} | "
        f"Pitch: {total_semitones:+g} st | Speed: {args.speed:g}x | SR: {target_sr} Hz"
    )
    if sr_note:
        print(f"  {sr_note}")
    print(
        f"  Safeguards: formant={formant}, transients={transients}, window={window}, "
        f"channels={channels}, headroom={args.headroom_db:+g}dB, "
        f"limiter={'off' if args.no_limiter else f'{args.ceiling_db:+g}dBFS'}"
    )
    if abs(total_semitones) >= 4.0 or args.speed <= 0.80 or args.speed >= 1.25:
        print(
            "  [WARN] Large shift detected (>= 4 semitones or >= 20% speed). "
            "For minimal drum/vocal artifacts on full mixes, consider `prepare --stems` "
            "and shifting drums (`--mode drums`) and vocals (`--mode vocal`) separately."
        )
    print(f"  Output ({'video+audio' if is_video_output else 'audio'}): {output_path}")

    if args.dry_run:
        print(f"  Audio Filter: {audio_filter}")
        print(f"  Command     : {' '.join(cmd)}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(cmd, check=True)
        _normalize_wav_header(output_path)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] FFmpeg failed with exit code {exc.returncode}", file=sys.stderr)
        return 1

    print(f"[OK] Saved: {output_path}")
    if output_path.suffix.lower() == ".wav":
        print(f'\n[NEXT] Verify technical QC:\n  python tools/antigravity/audio_cli.py qc "{output_path.parent}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
