---
name: audio-mix-engineer
description: >-
  Fix clipped or muddy audio, separate stems with local Demucs, run per-stem cleanup (declick, noise reduction, EQ, compression), and remix into a clean stereo WAV ready for mastering. Do NOT trigger for final LUFS loudness mastering or album/lyric generation.
---

# Audio Mix Engineer (Stems & Full-Mix Polish)

Repair distorted sources and polish stem or full-mix balance using `tools/antigravity/prepare_audio.py` and `tools/mixing/mix_tracks.py`. See [mix-presets-guide.md](./references/mix-presets-guide.md) for genre presets and stem layout details.

## Workflow

1. **Prepare audio (normalize, trim tail silence, de-clip, and separate stems)**:
   ```powershell
   python tools/antigravity/audio_cli.py prepare "<input>" -o "<work_dir>" --declip auto --trim-tail --stems
   ```
   - Omit `--stems` when polishing a full mix directly or when `<work_dir>\stems\<track>\*.wav` already exists.
   - Add `--declip always` if heavy brickwall distortion persists.
2. **Dry-run preview before writing files**:
   - **Stems mode**: `python tools/antigravity/audio_cli.py mix "<work_dir>" --genre "<genre>" --dry-run`
   - **Anti-Slop 6-Stem mode** (AI guitar/cymbal fizz & buried vocals; prepare with `--demucs-model htdemucs_6s`):
     `python tools/antigravity/audio_cli.py antislop-mix "<work_dir>" --preset band-analog --dry-run` (or `--preset rock-metal --measure-vb`)
   - **Full-mix mode**: `python tools/antigravity/audio_cli.py mix "<work_dir>\declipped" --full-mix --genre "<genre>" --dry-run`
   - **Pitch & Tempo Shifting (Distortion-Resistant)**:
     `python tools/antigravity/audio_cli.py pitch-tempo "<input>" --semitones 2 --speed 1.1 --mode vocal` (use `--mode instrumental` for non-vocal melodies; keeps MP4 A/V synced via `libx264`).
3. **Render polished stereo WAVs**:
   Re-run without `--dry-run` (writes to `<input_dir>\polished\`). Add `-j 0` to `mix` for parallel processing across albums.
   For overly dark or muffled stems lacking presence, optionally add upper-band harmonics cleanly via:
   ```powershell
   python tools/antigravity/audio_cli.py excite "<stem.wav>" --amount-db 2.0 --low-hz 600 --high-hz 12000
   ```
4. **Verify polished output**:
   ```powershell
   python tools/antigravity/audio_cli.py qc "<work_dir>\polished" --genre "<genre>"
   ```

## Guardrails

- **Stems are for balance, not surgery**: Stem bleed means narrow notches or heavy de-essing on one stem affect leaked instruments. Use broad tonal/level moves on stems.
- **FFmpeg compressor makeup**: Keep `makeup=1` on `acompressor` and `sidechaincompress` (linear multiplier, not dB) and apply gain via a separate `volume=...dB` filter.
- **Solo the named element first**: When fixing a specific issue ("vocals are buried" or "bass booms"), inspect the isolated `vocals.wav` / `bass.wav` stem before tuning other stems.
- **Silent stems (`< -40 dBFS` peak)** are automatically bypassed by `mix_tracks.py` so the de-clicker never alters noise-floor tracks.
- `mix_tracks.py` requires `--output-dir` to stay inside the `<input_dir>` passed on the command line (default: `polished`).

## Verification Checklist

- [ ] `<work_dir>\declipped\*.wav` shows reduced peak (`< 0.95`) when input was clipped
- [ ] `<work_dir>\polished\<track>.wav` exists and passes `qc` without `CLIPPING` errors
- [ ] Vocals remain audible against bass/synth without over-thinning kick impact
