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

## Available `mix-presets.yaml` Genres (72 built-in)

Use `--genre <name>` with any key from `tools/mixing/mix-presets.yaml`, including:
- **Pop / Electronic**: `pop`, `k-pop`, `hyperpop`, `electronic`, `edm`, `house`, `techno`, `trance`, `drum-and-bass`, `dubstep`, `synthwave`, `new-wave`, `dancehall`
- **Hip-Hop / R&B**: `hip-hop`, `hiphop`, `rap`, `trap`, `drill`, `phonk`, `grime`, `rnb`, `soul`, `funk`, `disco`, `gospel`
- **Rock / Metal / Punk**: `rock`, `indie-rock`, `alternative`, `grunge`, `punk`, `metal`, `metalcore`, `industrial`
- **Chill / Acoustic / Jazz / World**: `ambient`, `lo-fi`, `lofi`, `chillwave`, `trip-hop`, `vaporwave`, `shoegaze`, `folk`, `country`, `indie-folk`, `jazz`, `blues`, `classical`, `cinematic`, `latin`, `afrobeats`, `reggae`, `indie`, `singer-songwriter`
