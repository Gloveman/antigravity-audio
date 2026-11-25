#!/usr/bin/env python3
"""Anti-slop 6-stem mixing presets for AI-generated music remastering.

Cleans AI metallic guitar/cymbal fizz, carves vocal presence pockets, optionally
ducks backing guitars/synths via vocal sidechain, applies gentle tanh tape
warmth, and normalizes to mastering headroom (-3.0 dBFS default).

Reads either a single stem folder containing `vocals.wav` or a `prepare_audio.py`
work directory containing `stems/<track>/vocals.wav`.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


@dataclass(frozen=True)
class AntiSlopPreset:
    name: str
    description: str
    recommended_master_genre: str
    vocal_chain: str
    vocal_gain_db: float
    stem_chains: dict[str, str]
    sidechain_enabled: bool
    sidechain_stems: tuple[str, ...]
    sidechain_threshold: float
    sidechain_ratio: float
    sidechain_attack_ms: float
    sidechain_release_ms: float
    tape_drive: float
    tape_wet: float
    headroom_db: float = -3.0


PRESETS: dict[str, AntiSlopPreset] = {
    "band-analog": AntiSlopPreset(
        name="band-analog",
        description=(
            "Live band / indie rock anti-metallic polish: softens 3.4k/6.8k vocal glare, "
            "rolls off guitar >9.5kHz & cymbal >13.5kHz fizz, and adds subtle tape warmth."
        ),
        recommended_master_genre="indie-rock",
        vocal_chain=(
            "highpass=f=90,equalizer=f=240:t=q:w=1.0:g=1.5,"
            "equalizer=f=1800:t=q:w=1.2:g=1.8,equalizer=f=3400:t=q:w=2.2:g=-1.8,"
            "equalizer=f=6800:t=q:w=2.0:g=-3.0,lowpass=f=14500,"
            "acompressor=threshold=-16dB:ratio=2.2:attack=12:release=140:makeup=1"
        ),
        vocal_gain_db=2.2,
        stem_chains={
            "guitar": (
                "highpass=f=100,equalizer=f=280:t=q:w=1.1:g=1.5,"
                "equalizer=f=1800:t=q:w=1.0:g=-2.5,equalizer=f=4200:t=q:w=1.4:g=-3.5,"
                "treble=g=-4.0:f=7500,lowpass=f=9500,volume=-1.2dB"
            ),
            "drums": (
                "highpass=f=32,equalizer=f=85:t=q:w=1.2:g=1.5,"
                "equalizer=f=200:t=q:w=1.4:g=1.0,equalizer=f=4800:t=q:w=1.5:g=-2.5,"
                "treble=g=-4.0:f=8500,lowpass=f=13500,volume=-0.5dB"
            ),
            "bass": (
                "highpass=f=35,equalizer=f=220:t=q:w=1.2:g=-1.5,"
                "equalizer=f=750:t=q:w=1.2:g=1.0,volume=0.5dB"
            ),
            "other": (
                "highpass=f=140,equalizer=f=2000:t=q:w=1.0:g=-2.5,"
                "equalizer=f=6500:t=q:w=1.5:g=-4.0,lowpass=f=11000,volume=-2.0dB"
            ),
            "piano": (
                "highpass=f=120,equalizer=f=2000:t=q:w=1.0:g=-2.0,"
                "equalizer=f=6500:t=q:w=1.5:g=-3.0,lowpass=f=11500,volume=-1.5dB"
            ),
        },
        sidechain_enabled=False,
        sidechain_stems=("guitar", "other", "piano"),
        sidechain_threshold=0.055,
        sidechain_ratio=1.8,
        sidechain_attack_ms=15.0,
        sidechain_release_ms=180.0,
        tape_drive=0.14,
        tape_wet=0.60,
        headroom_db=-3.0,
    ),
    "rock-metal": AntiSlopPreset(
        name="rock-metal",
        description=(
            "Rock / metal vocal-forward anti-slop mix: husky 300Hz chest body, 4x12 guitar "
            "cabinet rolloff >8.8kHz, gentle 1.8:1 vocal-to-guitar/other sidechain, tight low end."
        ),
        recommended_master_genre="metal",
        vocal_chain=(
            "highpass=f=100,equalizer=f=300:t=q:w=1.0:g=2.5,"
            "equalizer=f=1700:t=q:w=1.1:g=1.5,equalizer=f=3200:t=q:w=1.8:g=-2.0,"
            "equalizer=f=6800:t=q:w=2.0:g=-3.0,lowpass=f=14500,"
            "acompressor=threshold=-19dB:ratio=2.2:attack=12:release=140:makeup=1"
        ),
        vocal_gain_db=3.6,
        stem_chains={
            "guitar": (
                "highpass=f=85,equalizer=f=280:t=q:w=0.9:g=3.2,"
                "equalizer=f=1700:t=q:w=1.1:g=-2.0,equalizer=f=3600:t=q:w=1.4:g=-3.8,"
                "treble=g=-4.5:f=6500,lowpass=f=8800,volume=0.2dB"
            ),
            "drums": (
                "highpass=f=36,equalizer=f=55:t=q:w=1.1:g=-3.0,"
                "equalizer=f=105:t=q:w=1.2:g=1.8,equalizer=f=230:t=q:w=1.3:g=1.6,"
                "equalizer=f=4600:t=q:w=1.5:g=-3.2,treble=g=-4.5:f=8000,"
                "lowpass=f=12500,volume=-0.3dB"
            ),
            "bass": (
                "highpass=f=38,equalizer=f=55:t=q:w=1.0:g=-3.8,"
                "equalizer=f=320:t=q:w=1.1:g=2.0,equalizer=f=850:t=q:w=1.2:g=2.2,"
                "volume=-0.2dB"
            ),
            "other": (
                "highpass=f=140,equalizer=f=2000:t=q:w=1.0:g=-2.5,"
                "lowpass=f=10000,volume=-2.0dB"
            ),
            "piano": (
                "highpass=f=130,equalizer=f=2000:t=q:w=1.0:g=-2.5,"
                "lowpass=f=10500,volume=-2.0dB"
            ),
        },
        sidechain_enabled=True,
        sidechain_stems=("guitar", "other", "piano"),
        sidechain_threshold=0.055,
        sidechain_ratio=1.8,
        sidechain_attack_ms=15.0,
        sidechain_release_ms=180.0,
        tape_drive=0.15,
        tape_wet=0.60,
        headroom_db=-3.0,
    ),
}

STEM_ORDER = ("vocals", "guitar", "drums", "bass", "other", "piano")
STEM_TAGS = {
    "vocals": "v",
    "guitar": "g",
    "drums": "d",
    "bass": "b",
    "other": "o",
    "piano": "p",
}
PIANO_MIN_PEAK_DB = -35.0
PIANO_MIN_RMS_DB = -55.0


def configure_stdio() -> None:
    """Ensure UTF-8 output on Windows consoles."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def require_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg must be installed and available on PATH.")


def _import_audio_libs():
    try:
        import numpy as np
        import soundfile as sf
        return np, sf
    except ModuleNotFoundError as exc:
        repo_root = Path(__file__).resolve().parents[2]
        raise RuntimeError(
            f"Missing dependency '{exc.name}'. Install audio dependencies with:\n"
            f'  pip install -r "{repo_root / "requirements-audio.txt"}"'
        ) from exc


def discover_track_stem_dirs(input_path: Path) -> list[tuple[str, Path]]:
    """Return [(track_name, stem_dir), ...] from a stem dir or work_dir."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    if (input_path / "vocals.wav").is_file():
        return [(input_path.name, input_path)]

    stems_root = input_path / "stems"
    if stems_root.is_dir():
        tracks = [
            (d.name, d)
            for d in sorted(stems_root.iterdir())
            if d.is_dir() and (d / "vocals.wav").is_file()
        ]
        if tracks:
            return tracks

    raise FileNotFoundError(
        f"No stems found under '{input_path}'. Expected either '<dir>/vocals.wav' "
        f"or '<work_dir>/stems/<track>/vocals.wav'."
    )


def _measure_wav_levels(wav_path: Path) -> tuple[float, float] | None:
    """Return (peak_db, rms_db) or None if numpy/soundfile are unavailable."""
    try:
        import numpy as np
        import soundfile as sf
    except ModuleNotFoundError:
        return None

    data, _ = sf.read(str(wav_path), dtype="float64")
    if data.size == 0:
        return -120.0, -120.0
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data ** 2)))
    peak_db = 20.0 * math.log10(peak + 1e-12)
    rms_db = 20.0 * math.log10(rms + 1e-12)
    return peak_db, rms_db


def resolve_stems(stem_dir: Path, piano_mode: str = "auto") -> tuple[list[tuple[str, Path]], list[str]]:
    """Select active stems in canonical order and collect advisory warnings."""
    notes: list[str] = []
    vocals_path = stem_dir / "vocals.wav"
    if not vocals_path.is_file():
        raise FileNotFoundError(f"Required stem missing: {vocals_path}")

    included: list[tuple[str, Path]] = [("vocals", vocals_path)]

    for name in ("guitar", "drums", "bass", "other"):
        p = stem_dir / f"{name}.wav"
        if p.is_file():
            included.append((name, p))
        elif name == "guitar":
            notes.append(
                "[WARN] guitar.wav not found — falling back to 4-stem layout. "
                "For best anti-slop results, separate with `--demucs-model htdemucs_6s`."
            )

    piano_path = stem_dir / "piano.wav"
    if piano_path.is_file():
        if piano_mode == "exclude":
            notes.append("[INFO] Skipped piano.wav (--no-piano).")
        elif piano_mode == "include":
            included.append(("piano", piano_path))
        else:
            levels = _measure_wav_levels(piano_path)
            if levels is None:
                notes.append(
                    "[INFO] Skipped piano.wav auto-check (numpy/soundfile not installed); "
                    "pass --include-piano to force inclusion."
                )
            else:
                peak_db, rms_db = levels
                if peak_db >= PIANO_MIN_PEAK_DB and rms_db >= PIANO_MIN_RMS_DB:
                    included.append(("piano", piano_path))
                else:
                    notes.append(
                        f"[INFO] Skipped silent piano.wav (peak={peak_db:.1f} dBFS, rms={rms_db:.1f} dBFS)."
                    )

    return included, notes


def build_filter_complex(
    preset: AntiSlopPreset,
    included_stems: list[tuple[str, Path]],
    vocal_gain_db: float,
    sidechain_enabled: bool,
    sidechain_ratio: float,
    weights: str | None = None,
) -> tuple[str, int]:
    """Build the FFmpeg filter_complex graph and return (graph, bus_count).

    Bus index 0 in the final amix is always `[vbus]` (vocals) so `--measure-vb`
    can isolate vocals (`1 0 ... 0`) and backing (`0 1 ... 1`) cleanly.
    """
    stem_names = [name for name, _ in included_stems]
    sc_targets = [name for name in stem_names if name in preset.sidechain_stems]
    use_sidechain = sidechain_enabled and len(sc_targets) > 0

    parts: list[str] = []

    # Input 0 is always vocals.wav
    if use_sidechain:
        parts.append(
            f"[0:a]{preset.vocal_chain},asplit=2[vm][vsc];"
            f"[vm]volume={vocal_gain_db:g}dB[vbus]"
        )
    else:
        parts.append(f"[0:a]{preset.vocal_chain},volume={vocal_gain_db:g}dB[vbus]")

    # Non-vocal stems
    for idx, (name, _) in enumerate(included_stems):
        if idx == 0:
            continue
        tag = STEM_TAGS[name]
        chain = preset.stem_chains[name]
        parts.append(f"[{idx}:a]{chain}[{tag}]")

    buses: list[str] = ["vbus"]

    if use_sidechain:
        sc_params = (
            f"sidechaincompress=threshold={preset.sidechain_threshold:g}:"
            f"ratio={sidechain_ratio:g}:attack={preset.sidechain_attack_ms:g}:"
            f"release={preset.sidechain_release_ms:g}:makeup=1"
        )
        if len(sc_targets) >= 2:
            sc_inputs = "".join(f"[{STEM_TAGS[n]}]" for n in sc_targets)
            parts.append(
                f"{sc_inputs}amix=inputs={len(sc_targets)}:normalize=0:dropout_transition=0[sc_bed]"
            )
            parts.append(f"[sc_bed][vsc]{sc_params}[gob]")
        else:
            parts.append(f"[{STEM_TAGS[sc_targets[0]]}][vsc]{sc_params}[gob]")
        buses.append("gob")
        for name in stem_names[1:]:
            if name not in sc_targets:
                buses.append(STEM_TAGS[name])
    else:
        for name in stem_names[1:]:
            buses.append(STEM_TAGS[name])

    bus_inputs = "".join(f"[{b}]" for b in buses)
    weight_opt = f":weights='{weights}'" if weights else ""
    parts.append(
        f"{bus_inputs}amix=inputs={len(buses)}:normalize=0:dropout_transition=0{weight_opt}[mixed]"
    )

    return ";".join(parts), len(buses)


def render_ffmpeg_bus(
    included_stems: list[tuple[str, Path]],
    filter_complex: str,
    sample_rate: int,
):
    """Run FFmpeg filter_complex into a temporary float32 WAV and return (data, sr)."""
    np, sf = _import_audio_libs()
    with tempfile.TemporaryDirectory(prefix="antislop_") as tmpdir:
        tmp_wav = Path(tmpdir) / "bus_f32.wav"
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
        for _, stem_path in included_stems:
            cmd.extend(["-i", str(stem_path)])
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[mixed]",
            "-ar", str(sample_rate),
            "-ac", "2",
            "-c:a", "pcm_f32le",
            str(tmp_wav),
        ])
        subprocess.run(cmd, check=True)
        data, sr = sf.read(str(tmp_wav), dtype="float64")
    return data, sr


def measure_vb_balance(
    preset: AntiSlopPreset,
    included_stems: list[tuple[str, Path]],
    vocal_gain_db: float,
    sidechain_enabled: bool,
    sidechain_ratio: float,
    bus_count: int,
    sample_rate: int,
) -> float | None:
    """Render vocal-only and backing-only buses and print active 10s V-B deltas."""
    if bus_count < 2:
        print("[V-B] Skipping measurement (fewer than 2 buses).")
        return None

    np, _ = _import_audio_libs()
    v_weights = " ".join(["1"] + ["0"] * (bus_count - 1))
    b_weights = " ".join(["0"] + ["1"] * (bus_count - 1))

    v_graph, _ = build_filter_complex(
        preset, included_stems, vocal_gain_db, sidechain_enabled, sidechain_ratio, weights=v_weights
    )
    b_graph, _ = build_filter_complex(
        preset, included_stems, vocal_gain_db, sidechain_enabled, sidechain_ratio, weights=b_weights
    )

    voc, sr = render_ffmpeg_bus(included_stems, v_graph, sample_rate)
    rest, _ = render_ffmpeg_bus(included_stems, b_graph, sample_rate)

    vm = voc.mean(axis=1) if voc.ndim > 1 else voc
    rm = rest.mean(axis=1) if rest.ndim > 1 else rest
    win = 10 * sr

    def _db(x: float) -> float:
        return float(20.0 * math.log10(x + 1e-9))

    vb_rows: list[tuple[int, float, float, float]] = []
    if len(vm) <= win:
        v = float(np.sqrt(np.mean(vm ** 2)))
        r = float(np.sqrt(np.mean(rm ** 2)))
        if _db(v) > -35.0:
            vb_rows.append((0, _db(v), _db(r), _db(v / (r + 1e-9))))
    else:
        for s in range(0, len(vm) - win, win):
            v = float(np.sqrt(np.mean(vm[s : s + win] ** 2)))
            r = float(np.sqrt(np.mean(rm[s : s + win] ** 2)))
            if _db(v) > -35.0:
                vb_rows.append((s // sr, _db(v), _db(r), _db(v / (r + 1e-9))))

    if not vb_rows:
        print("[V-B] No active vocal windows (> -35 dBFS) detected.")
        return None

    for t, v_db, r_db, d_db in vb_rows:
        print(f"  {t:>3}-{t + 10:<3}s voc={v_db:+.1f} band={r_db:+.1f} V-B={d_db:+.1f}")
    median_vb = float(np.median([row[3] for row in vb_rows]))
    print(f"[V-B] Median active V-B: {median_vb:+.1f} dB")
    return median_vb


def apply_tape_warmth_and_headroom(
    data,
    drive: float,
    wet: float,
    use_warmth: bool,
    headroom_db: float,
):
    """Apply parallel tanh saturation and peak-normalize to headroom_db."""
    np, _ = _import_audio_libs()
    out = data
    if use_warmth and drive > 0.0 and wet > 0.0:
        gain = 1.0 + drive * 2.5
        x_sat = np.tanh(out * gain) / math.tanh(gain)
        out = wet * x_sat + (1.0 - wet) * out

    target_peak = 10.0 ** (headroom_db / 20.0)
    peak = float(np.max(np.abs(out)))
    if peak > 0.0:
        out = out * (target_peak / peak)
    return out


def resolve_output_path(
    input_path: Path,
    is_single_stem_dir: bool,
    track_name: str,
    stem_dir: Path,
    output_arg: str | None,
) -> Path:
    if is_single_stem_dir:
        if output_arg:
            out_p = Path(output_arg).expanduser().resolve()
            if out_p.suffix.lower() == ".wav":
                return out_p
            return out_p / f"{track_name}.wav"
        if stem_dir.parent.name == "stems":
            return stem_dir.parent.parent / "polished" / f"{track_name}.wav"
        return stem_dir.parent / f"{track_name}_antislop.wav"

    out_dir = Path(output_arg).expanduser().resolve() if output_arg else (input_path / "polished")
    return out_dir / f"{track_name}.wav"


def print_presets() -> None:
    print("Available anti-slop 6-stem presets:\n")
    for name, p in PRESETS.items():
        sc_info = (
            f"on (ratio={p.sidechain_ratio:g}, thresh={p.sidechain_threshold:g}, "
            f"targets={','.join(p.sidechain_stems)})"
            if p.sidechain_enabled
            else "off"
        )
        print(f"  {name}")
        print(f"    Description : {p.description}")
        print(f"    Vocal gain  : {p.vocal_gain_db:+.1f} dB")
        print(f"    Sidechain   : {sc_info}")
        print(f"    Tape warmth : drive={p.tape_drive:g}, wet={p.tape_wet:.0%}, headroom={p.headroom_db:+.1f} dBFS")
        print(f"    Master hint : --genre {p.recommended_master_genre} --linear-phase-eq --deess --bass-mono-freq 100 --ceiling -1.2\n")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="antislop_mix.py",
        description="Apply verified 6-stem anti-slop EQ, vocal pocket, sidechain, and analog warmth presets.",
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        help="Stem directory (containing vocals.wav) or prepare_audio work directory (containing stems/<track>/).",
    )
    parser.add_argument(
        "-p", "--preset",
        choices=list(PRESETS.keys()),
        default="band-analog",
        help="Anti-slop mix preset (default: band-analog).",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Print available presets and their parameters, then exit.",
    )
    parser.add_argument(
        "-o", "--output",
        help="Output WAV file (single stem dir) or output directory (default: <work_dir>/polished).",
    )
    parser.add_argument("--vocal-gain-db", type=float, default=None, help="Override preset vocal bus gain in dB.")
    parser.add_argument("--drive", type=float, default=None, help="Override tanh tape saturation drive (default: preset).")
    parser.add_argument("--wet", type=float, default=None, help="Override tanh tape wet mix 0.0-1.0 (default: preset).")
    parser.add_argument("--no-warmth", action="store_true", help="Disable tanh tape saturation stage.")
    parser.add_argument("--sidechain-ratio", type=float, default=None, help="Override sidechain compression ratio (>= 1.0).")
    parser.add_argument("--no-sidechain", action="store_true", help="Disable vocal-to-backing sidechain compression.")
    parser.add_argument("--headroom-db", type=float, default=None, help="Peak headroom ceiling in dBFS (default: -3.0).")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Output sample rate in Hz (default: 44100).")

    piano_group = parser.add_mutually_exclusive_group()
    piano_group.add_argument("--include-piano", action="store_true", help="Force-include piano.wav even if quiet.")
    piano_group.add_argument("--no-piano", action="store_true", help="Always exclude piano.wav.")

    parser.add_argument("--measure-vb", action="store_true", help="Measure active 10s vocal-to-backing (V-B) balance in dB.")
    parser.add_argument("--dry-run", action="store_true", help="Preview stem discovery, filter graph, and output paths without rendering.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    configure_stdio()
    args = parse_args(argv)

    if args.list_presets:
        print_presets()
        return 0

    if not args.input_path:
        print("[ERROR] input_path is required unless --list-presets is set.", file=sys.stderr)
        return 2

    preset = PRESETS[args.preset]
    vocal_gain_db = preset.vocal_gain_db if args.vocal_gain_db is None else args.vocal_gain_db
    drive = preset.tape_drive if args.drive is None else args.drive
    wet = preset.tape_wet if args.wet is None else args.wet
    headroom_db = preset.headroom_db if args.headroom_db is None else args.headroom_db
    sidechain_enabled = False if args.no_sidechain else preset.sidechain_enabled
    sidechain_ratio = preset.sidechain_ratio if args.sidechain_ratio is None else args.sidechain_ratio

    if drive < 0.0:
        print("[ERROR] --drive must be >= 0.0", file=sys.stderr)
        return 2
    if not (0.0 <= wet <= 1.0):
        print("[ERROR] --wet must be between 0.0 and 1.0", file=sys.stderr)
        return 2
    if headroom_db > 0.0:
        print("[ERROR] --headroom-db must be <= 0.0", file=sys.stderr)
        return 2
    if sidechain_ratio < 1.0:
        print("[ERROR] --sidechain-ratio must be >= 1.0", file=sys.stderr)
        return 2
    if args.sample_rate <= 0:
        print("[ERROR] --sample-rate must be > 0", file=sys.stderr)
        return 2

    piano_mode = "include" if args.include_piano else ("exclude" if args.no_piano else "auto")

    try:
        if not args.dry_run:
            require_ffmpeg()
        input_path = Path(args.input_path).expanduser().resolve()
        tracks = discover_track_stem_dirs(input_path)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    is_single_stem_dir = (input_path / "vocals.wav").is_file()
    rendered_dirs: set[Path] = set()

    for track_name, stem_dir in tracks:
        try:
            included_stems, notes = resolve_stems(stem_dir, piano_mode=piano_mode)
        except FileNotFoundError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

        filter_complex, bus_count = build_filter_complex(
            preset=preset,
            included_stems=included_stems,
            vocal_gain_db=vocal_gain_db,
            sidechain_enabled=sidechain_enabled,
            sidechain_ratio=sidechain_ratio,
        )
        out_wav = resolve_output_path(
            input_path=input_path,
            is_single_stem_dir=is_single_stem_dir,
            track_name=track_name,
            stem_dir=stem_dir,
            output_arg=args.output,
        )
        rendered_dirs.add(out_wav.parent)

        stem_list = ", ".join(name for name, _ in included_stems)
        print(f"[antislop-mix] Track: {track_name} | Preset: {preset.name} | Stems: {stem_list}")
        for note in notes:
            print(f"  {note}")
        print(
            f"  Settings: vocal_gain={vocal_gain_db:+.1f}dB, "
            f"sidechain={'on (ratio=' + f'{sidechain_ratio:g})' if sidechain_enabled else 'off'}, "
            f"warmth={'off' if args.no_warmth else f'drive={drive:g} wet={wet:.0%}'}, "
            f"headroom={headroom_db:+.1f}dBFS"
        )
        print(f"  Output  : {out_wav}")

        if args.dry_run:
            print(f"  Filter  : {filter_complex}")
            continue

        try:
            if args.measure_vb:
                measure_vb_balance(
                    preset=preset,
                    included_stems=included_stems,
                    vocal_gain_db=vocal_gain_db,
                    sidechain_enabled=sidechain_enabled,
                    sidechain_ratio=sidechain_ratio,
                    bus_count=bus_count,
                    sample_rate=args.sample_rate,
                )

            data, sr = render_ffmpeg_bus(included_stems, filter_complex, args.sample_rate)
            processed = apply_tape_warmth_and_headroom(
                data=data,
                drive=drive,
                wet=wet,
                use_warmth=not args.no_warmth,
                headroom_db=headroom_db,
            )
            np, sf = _import_audio_libs()
            out_wav.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(out_wav), processed, sr, subtype="PCM_24")
            final_peak = float(np.max(np.abs(processed)))
            print(f"[OK] Saved {out_wav} (sr={sr}, peak={final_peak:.4f})")
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

    if not args.dry_run and rendered_dirs:
        target_dir = sorted(rendered_dirs)[0]
        print(
            f"\n[NEXT] Master with:\n"
            f'  python tools/antigravity/audio_cli.py master "{target_dir}" '
            f"--genre {preset.recommended_master_genre} --linear-phase-eq --deess --bass-mono-freq 100 --ceiling -1.2"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
