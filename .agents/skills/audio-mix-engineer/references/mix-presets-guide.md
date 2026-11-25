# Mix Presets & Demucs Bridge Reference

## Directory Layout Expected by `mix_tracks.py`

### Stems Mode (default)
```text
<work_dir>/
  raw/<track>.wav
  declipped/<track>.wav
  stems/
    <track>/
      vocals.wav
      drums.wav
      bass.wav
      other.wav          # htdemucs 4-stem; htdemucs_6s adds guitar.wav, piano.wav
  polished/<track>.wav   # output written here
```

`mix_tracks.py` routes WAV filenames inside `<work_dir>/stems/<track>/` automatically by keyword (`backing_vocal`, `vocal`, `percussion`, `drum`, `bass`, `guitar`, `keyboard`/`piano`, `strings`, `brass`, `woodwinds`, `synth`, `other`). Both Demucs 4/6-stem outputs and 12-stem splits work seamlessly.

### Full-Mix Mode (`--full-mix`)
Pass the folder containing WAV files directly (e.g. `<work_dir>/declipped`) with `--full-mix`:
- Outputs go to `<that_folder>/polished/`.

## `prepare_audio.py` Key Flags

| Flag | Default | Purpose |
| :--- | :--- | :--- |
| `--declip` | `auto` | Runs `-3 dB` headroom + FFmpeg `adeclip` when peak `>= 0.985` (`always` / `never` also valid) |
| `--headroom-db` | `-3.0` | Pre-declip gain adjustment in dB |
| `--trim-tail` | off | Detects `>= 2s` trailing silence below `-60 dBFS` and applies a `1.5s` fade-out |
| `--stems` | off | Runs `python -m demucs` and stages WAVs into `<work_dir>/stems/<track>/` |
| `--demucs-model` | `htdemucs` | Use `htdemucs` (4 stems) or `htdemucs_6s` (6 stems) |
| `--device` | `cpu` | `cpu` or `cuda` |

## Harmonic Excitation (`audio_cli.py excite`)

For dark or muffled stems (e.g. `bass` or dull `vocals`), `excite <input.wav> [--amount-db 2.0] [--low-hz 600] [--high-hz 12000] [--drive 20.0]` applies full-band `tanh` saturation followed by `HP(saturated) - HP(original)` differencing (`tools/mixing/excitation.py`), adding upper harmonics without bloating sub-bass. Use lower `--drive` (e.g. `2.0`–`5.0`) on louder signals; default `20.0` is calibrated for quiet dark stems, and avoid on already bright or metallic AI tracks.

## Anti-Slop 6-Stem Presets (`audio_cli.py antislop-mix`)

For AI-generated rock/band tracks separated with `prepare_audio.py --stems --demucs-model htdemucs_6s`, `antislop-mix` targets metallic guitar/cymbal fizz and buried vocals:

| Preset | Profile | Vocal Gain | Sidechain | Warmth | Recommended Master Follow-Up |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `band-analog` | Indie / girl-band live polish, guitar `>9.5 kHz` & cymbal `>13.5 kHz` rolloff | `+2.2 dB` | Off | `drive=0.14`, `60%` wet | `--genre indie-rock --linear-phase-eq --deess --bass-mono-freq 100 --ceiling -1.2` |
| `rock-metal` | Heavy rock/metal 4x12 guitar cabinet `>8.8 kHz` cut, 300 Hz husky vocal chest | `+3.6 dB` | `1.8:1` on `guitar/other/piano` | `drive=0.15`, `60%` wet | `--genre metal --linear-phase-eq --deess --bass-mono-freq 100 --ceiling -1.2` |

- **Key flags**: `--list-presets`, `--measure-vb` (active 10s vocal-to-backing dB balance), `--vocal-gain-db`, `--drive`, `--no-sidechain`, `--dry-run`.
- **Silent `piano.wav` auto-bypass**: Quiet bleed-only `piano.wav` stems (`peak < -35 dBFS` or `rms < -55 dBFS`) are skipped automatically unless `--include-piano` is passed.

## Pitch & Tempo Shifting (`audio_cli.py pitch-tempo`)

Uses FFmpeg's `rubberband` engine with `pitchq=quality`, `channels=together` (stereo phase coherence), `-3.0 dB` pre-shift headroom, and a `-1.0 dBFS` safety `alimiter` ceiling:

| Mode | Formant | Transients / Detector | Window | Best For |
| :--- | :--- | :--- | :--- | :--- |
| `vocal` (default) | `preserved` | `mixed` / `compound` | `standard` | Full songs & singing vocals |
| `instrumental` | `shifted` | `crisp` / `compound` | `standard` | Melodies, whistle, acoustic/synth |
| `drums` | `shifted` | `crisp` / `percussive` | `short` | Drum stems (minimal pre-echo) |
| `smooth` | `preserved` | `smooth` / `soft` | `long` | Pads, strings, sustained ballads |

- **Video A/V sync**: Video inputs (`.mp4`, `.mkv`, `.mov`, `.webm`) keep sync automatically (`-c:v copy` when `--speed 1.0`, or `setpts=PTS/speed` + `libx264` when speed changes).
- **Large shifts (`>= ±4` semitones or `>= ±20%` speed)**: Separate stems first (`prepare --stems`) and shift `drums.wav` (`--mode drums`) and `vocals.wav` (`--mode vocal`) independently to prevent transient smearing.

## Available `mix-presets.yaml` Genres (72 built-in)

Use `--genre <name>` with any key from `tools/mixing/mix-presets.yaml`, including:
- **Pop / Electronic**: `pop`, `k-pop`, `hyperpop`, `electronic`, `edm`, `house`, `techno`, `trance`, `drum-and-bass`, `dubstep`, `synthwave`, `new-wave`, `dancehall`
- **Hip-Hop / R&B**: `hip-hop`, `hiphop`, `rap`, `trap`, `drill`, `phonk`, `grime`, `rnb`, `soul`, `funk`, `disco`, `gospel`
- **Rock / Metal / Punk**: `rock`, `indie-rock`, `alternative`, `grunge`, `punk`, `metal`, `metalcore`, `industrial`
- **Chill / Acoustic / Jazz / World**: `ambient`, `lo-fi`, `lofi`, `chillwave`, `trip-hop`, `vaporwave`, `shoegaze`, `folk`, `country`, `indie-folk`, `jazz`, `blues`, `classical`, `cinematic`, `latin`, `afrobeats`, `reggae`, `indie`, `singer-songwriter`
