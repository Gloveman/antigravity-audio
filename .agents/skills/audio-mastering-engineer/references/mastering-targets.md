# Mastering Targets & CLI Flags Reference

## Loudness & Ceiling Guidelines

| Use Case / Genre | Typical Target LUFS | True Peak Ceiling | Recommended Flags |
| :--- | :--- | :--- | :--- |
| Universal Streaming (Spotify, YouTube, Apple) | `-14.0 LUFS` | `-1.0 dBTP` | `--target-lufs -14.0 --ceiling -1.0` |
| Club / EDM / House / Hip-Hop Remix | `-11.0` to `-9.5 LUFS` | `-1.0 dBTP` | `--genre edm --target-lufs -10.5 --bass-mono-freq 120` |
| Pop / Rock / K-Pop | `-13.5` to `-11.5 LUFS` | `-1.0 dBTP` | `--genre pop` or `--genre k-pop` |
| Jazz / Classical / Acoustic | `-18.0` to `-15.5 LUFS` | `-1.0 dBTP` | `--genre jazz` / `--genre acoustic` |

## High-Value `master` (`master_tracks.py`) Flags

- `--genre <name>`: Loads defaults from `tools/mastering/genre-presets.yaml` (406 genres: `pop`, `k-pop`, `hip-hop`, `edm`, `bass-house`, `synthwave`, `rock`, `indie-folk`, `jazz`, `cinematic`, etc.).
- `--target-lufs <float>` / `--ceiling <float>`: Override target LUFS and true-peak limiter ceiling.
- `--linear-phase-eq`: Use zero-phase FIR EQ instead of IIR for transparent cuts (`--cut-highmid`, `--cut-highs`).
- `--bass-mono-freq <hz>`: Mono-sums sub-bass frequencies (e.g. `100–120 Hz`) for clean club/PA translation.
- `--deess` / `--multiband`: Enable de-esser or 3-band dynamics control when needed.
- `--album-consistency <db>`: Caps LUFS variance across all WAVs in an album folder (recommended `1.0`).
- `--output-bits 24` / `--output-sample-rate 48000`: Hi-res export options when source supports them.
