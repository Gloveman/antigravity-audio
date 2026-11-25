# Antigravity Audio Quick Reference (`antigravity-audio`)

This branch adapts the audio-processing engine of [`bitwize-music-studio/claude-ai-music-skills`](https://github.com/bitwize-music-studio/claude-ai-music-skills) (CC0-1.0) for **Google Antigravity 2.0** and **local audio/video workflows** without requiring Suno MCP or Claude Code plugins. See [README.md](README.md) for the full guide.

---

## Added Files

- `requirements-audio.txt` — Audio-only Python dependencies (no Playwright, PostgreSQL, AWS S3, or MCP extras).
- `tools/antigravity/prepare_audio.py` — Converts audio to 44.1 kHz stereo WAV, trims trailing silence (`--trim-tail`), repairs digital clipping via `adeclip` (`--declip auto`), and runs local Demucs (`--stems`).
- `tools/antigravity/antislop_mix.py` — 6-stem anti-slop mixer (`band-analog`, `rock-metal`) for AI metallic guitar/cymbal cleanup, vocal pockets, sidechain ducking, and `tanh` analog warmth.
- `tools/antigravity/pitch_tempo.py` — Distortion-resistant Rubber Band pitch & tempo shifter (`vocal`, `instrumental`, `drums`, `smooth`) with `-3 dB` pre-headroom, `-1 dBFS` safety ceiling, and synced `libx264` video output.
- `tools/antigravity/audio_cli.py` — Unified CLI dispatcher (`prepare`, `qc`, `analyze`, `mix`, `antislop-mix`, `pitch-tempo`, `excite`, `master`, `ref-master`, `fix-dynamics`, `mono-check`, `adm-check`, `codec-preview`).
- `.agents/skills/` — 3 Antigravity 2.0 skills:
  - [`audio-qc-analyzer`](.agents/skills/audio-qc-analyzer/SKILL.md)
  - [`audio-mix-engineer`](.agents/skills/audio-mix-engineer/SKILL.md)
  - [`audio-mastering-engineer`](.agents/skills/audio-mastering-engineer/SKILL.md)

Upstream files in `skills/`, `tools/mixing/`, `tools/mastering/`, and `servers/` are left untouched.

---

## Quick Command Cheat Sheet

```powershell
# 1. Setup
pip install -r requirements-audio.txt
pip install demucs

# 2. Prepare + 4-stem split
python tools/antigravity/audio_cli.py prepare "track.mp3" -o "./work_audio" --declip auto --trim-tail --stems

# 3. QC & Loudness Analysis
python tools/antigravity/audio_cli.py qc "./work_audio/declipped" --genre edm
python tools/antigravity/audio_cli.py analyze "./work_audio/declipped"

# 4. Mix (72-genre stems/full-mix OR 6-stem anti-slop)
python tools/antigravity/audio_cli.py mix "./work_audio" --genre edm
python tools/antigravity/audio_cli.py antislop-mix "./work_rock" --preset rock-metal --measure-vb

# 5. Master & Verify
python tools/antigravity/audio_cli.py master "./work_audio/polished" --genre edm --target-lufs -10.5 --ceiling -1.2 --bass-mono-freq 110 --linear-phase-eq
python tools/antigravity/audio_cli.py qc "./work_audio/polished/mastered" --genre edm
python tools/antigravity/audio_cli.py mono-check "./work_audio/polished/mastered"
python tools/antigravity/audio_cli.py adm-check "./work_audio/polished/mastered" --ceiling -1.2
python tools/antigravity/audio_cli.py codec-preview "./work_audio/polished/mastered/track.wav" -b 128

# Optional utilities
python tools/antigravity/audio_cli.py excite "./work_audio/stems/track/vocals.wav" --amount-db 2.0
python tools/antigravity/audio_cli.py pitch-tempo "track.mp4" --semitones 2 --speed 1.1 --mode vocal
```
