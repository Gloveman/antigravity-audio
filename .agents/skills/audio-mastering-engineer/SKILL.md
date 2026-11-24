---
name: audio-mastering-engineer
description: >-
  Master polished stereo WAVs to streaming/club loudness (LUFS), match tonal balance to a reference track via matchering, tame dynamic spikes, and verify true peak ceiling and mono/AAC compatibility. Do NOT trigger for stem splitting or raw mix EQ.
---

# Audio Mastering Engineer

Master polished WAVs using genre presets (`master_tracks.py`), reference matching (`reference_master.py`), and dynamics repair (`fix_dynamic_track.py`). Target tables and flag lists live in [mastering-targets.md](./references/mastering-targets.md).

## Workflow

1. **Analyze pre-master levels**:
   ```powershell
   python tools/antigravity/audio_cli.py analyze "<wav_dir>"
   ```
2. **Choose mastering path**:
   - **Standard / Genre preset mastering** (supports 406 genres, dry-run first):
     ```powershell
     python tools/antigravity/audio_cli.py master "<wav_dir>" --genre "<genre>" --ceiling -1.0 --dry-run
     python tools/antigravity/audio_cli.py master "<wav_dir>" --genre "<genre>" --ceiling -1.0
     ```
     Override target loudness with `--target-lufs` (e.g., `-14.0` streaming, `-10.5` club/EDM) and add `--album-consistency 1.0` when mastering multi-track releases.
   - **Reference-track tonal/loudness matching (`matchering`)**:
     ```powershell
     python tools/antigravity/audio_cli.py ref-master --reference "<pro_ref.wav>" --target "<track.wav>" --output-dir "<mastered_dir>"
     ```
   - **Excessive dynamic range fix** (when dynamics exceed genre target):
     ```powershell
     python tools/antigravity/audio_cli.py fix-dynamics "<input.wav>" "<input_dir>\mastered\<name>.wav"
     ```
3. **Run post-master verification**:
   ```powershell
   python tools/antigravity/audio_cli.py qc "<wav_dir>\mastered" --genre "<genre>"
   python tools/antigravity/audio_cli.py mono-check "<wav_dir>\mastered"
   python tools/antigravity/audio_cli.py adm-check "<wav_dir>\mastered" --ceiling -1.0
   python tools/antigravity/audio_cli.py codec-preview "<wav_dir>\mastered\<track>.wav" -b 128
   ```

## Guardrails

- Keep True Peak ceiling at `-1.0 dBTP` (or lower) so lossy AAC/MP3 transcoding does not clip.
- `master_tracks.py` checks `<path>\originals\` before `<path>`, and requires `--output-dir` to stay inside `<path>` (default: `mastered`).
- Never chain `master` twice on already-mastered audio; go back to `polished/` or raw mixes.

## Verification Checklist

- [ ] Integrated LUFS matches target (`-14 LUFS` streaming or genre preset)
- [ ] `qc` passes `clipping` and `truepeak` (`<= -1.0 dBTP`)
- [ ] `mono-check` passes with no critical phase cancellation
