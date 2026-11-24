---
name: audio-qc-analyzer
description: >-
  Audit WAV/audio tracks for clipping, true peak, clicks, silence, mono-fold phase drops, loudness (LUFS), dynamics, and codec distortion using standalone CLI tools. Do NOT trigger when mixing stems, mastering audio, or writing Suno lyrics/prompts.
---

# Audio QC & Loudness Analyzer

Inspect local audio files before and after mixing or mastering via `tools/antigravity/audio_cli.py`. Detailed check definitions and thresholds live in [qc-checks.md](./references/qc-checks.md).

## Workflow

1. **Normalize non-WAV sources first** (skip if directory already contains 44.1/48 kHz WAVs):
   ```powershell
   python tools/antigravity/audio_cli.py prepare "<input-file-or-dir>" -o "<work_dir>" --declip never
   ```
2. **Run 8-point technical QC** (`format`, `mono`, `phase`, `clipping`, `truepeak`, `clicks`, `silence`, `spectral`):
   ```powershell
   python tools/antigravity/audio_cli.py qc "<wav_dir>" --genre "<genre>"
   ```
   Pass `--genre` for electronic, metal, or IDM tracks so intentional sharp transients do not fail the click detector.
3. **Measure LUFS, dynamic range, and vocal-to-mix balance**:
   ```powershell
   python tools/antigravity/audio_cli.py analyze "<wav_dir>"
   ```
4. **Verify mono compatibility and lossy codec translation** (for final masters):
   ```powershell
   python tools/antigravity/audio_cli.py mono-check "<wav_dir>"
   python tools/antigravity/audio_cli.py codec-preview "<wav_dir>\<track>.wav" -b 128
   ```

## Guardrails

- Run `qc` before mixing/mastering to catch upstream clipping (`> -1.0 dBTP`) or dead trailing silence (`--trim-tail`).
- If `qc` reports `CLIPPING` or `TRUEPEAK` failures on a source file, route to `audio-mix-engineer` (`prepare --declip auto`) before mastering.
- `mono-check` exits non-zero when any frequency band drops below `-6.0 dB` in mono fold-down (phase cancellation).

## Verification Checklist

- [ ] `qc` reports `0 FAIL` across all target WAV files
- [ ] `analyze` shows True Peak `<= -1.0 dBFS` and expected LUFS range
- [ ] `mono-check` verdict is `PASS` or `WARN` (zero `FAIL`)
