# Antigravity Audio

Standalone local audio engineering CLI and [Google Antigravity](https://antigravity.google) 2.0 skills for technical QC, Demucs stem separation, anti-slop mixing, distortion-resistant Rubber Band pitch/tempo shifting, and streaming/club mastering.

Adapted from the audio-processing engine of [`bitwize-music-studio/claude-ai-music-skills`](https://github.com/bitwize-music-studio/claude-ai-music-skills) (CC0-1.0) for **local audio files** (`.wav`, `.mp3`, `.flac`, `.m4a`, `.webm`, `.ogg`, `.opus`) and **video files** (`.mp4`, `.mkv`, `.mov`, `.webm`) **without requiring Suno MCP, PostgreSQL, Playwright, or Claude Code plugins**.

> [!NOTE]
> Development on this fork happens on the `antigravity-audio` branch using an **additive-only** layout (`tools/antigravity/`, `.agents/skills/`, `requirements-audio.txt`, `README.md`, `ANTIGRAVITY.md`). Upstream `skills/`, `tools/mixing/`, `tools/mastering/`, and `servers/` remain untouched so `upstream/main` updates merge cleanly.

---

## Key Capabilities

| Area | Subcommands | What It Does |
| :--- | :--- | :--- |
| **Input & Stems** | `prepare` | Converts audio to 44.1 kHz stereo WAV, trims trailing silence (`--trim-tail`), repairs digital clipping via FFmpeg `adeclip` (`--declip auto`), and runs local Demucs (`htdemucs` / `htdemucs_6s`) |
| **Mixing & Anti-Slop** | `mix`, `antislop-mix`, `excite` | 72-genre stem/full-mix cleanup (`mix`), 6-stem AI guitar/cymbal fizz removal + vocal pocket presets (`band-analog`, `rock-metal`), and upper-harmonic excitation for dark stems (`excite`) |
| **Pitch & Tempo** | `pitch-tempo` | FFmpeg `rubberband` shifting (`vocal`, `instrumental`, `drums`, `smooth`) with `pitchq=quality`, `channels=together`, `-3 dB` pre-headroom, `-1 dBFS` safety limiter, and synced `libx264` MP4 video output |
| **Mastering** | `master`, `ref-master`, `fix-dynamics` | 406-genre LUFS/true-peak mastering with linear-phase EQ & bass-mono summing (`master`), reference track matching via `matchering` (`ref-master`), and excessive dynamic-range repair |
| **QC & Validation** | `qc`, `analyze`, `mono-check`, `adm-check`, `codec-preview` | 8-check technical QC, LUFS/spectral balance analysis, stereo-to-mono fold-down check, 256k AAC inter-sample clipping check (`adm-check`), and 128k AAC auditioning |

---

## Quick Setup

Requires **Python 3.11+** and **FFmpeg / FFprobe** on `PATH` (with `librubberband` enabled for `pitch-tempo`).

```powershell
# 1. Install audio-only Python dependencies
pip install -r requirements-audio.txt

# 2. (Optional) Install local AI stem separation (Demucs)
pip install demucs

# 3. Verify FFmpeg & Rubber Band filter availability
ffmpeg -version
ffmpeg -hide_banner -filters | Select-String rubberband
```

Verify the CLI entry point:

```powershell
python tools/antigravity/audio_cli.py --help
```

---

## Common Workflows

### 1. Standard Remastering Pipeline (Stems or Full-Mix)

```powershell
# Prepare audio: normalize, de-clip, trim dead tail silence, and split 4 stems
python tools/antigravity/audio_cli.py prepare "track.mp3" -o "./work_audio" --declip auto --trim-tail --stems

# Audit technical QC and loudness/spectral balance
python tools/antigravity/audio_cli.py qc "./work_audio/declipped" --genre edm
python tools/antigravity/audio_cli.py analyze "./work_audio/declipped"

# Preview and render polished mix (or pass "./work_audio/declipped --full-mix")
python tools/antigravity/audio_cli.py mix "./work_audio" --genre edm --dry-run
python tools/antigravity/audio_cli.py mix "./work_audio" --genre edm

# Master to target LUFS with true-peak ceiling and sub-bass mono alignment
python tools/antigravity/audio_cli.py master "./work_audio/polished" --genre edm --target-lufs -10.5 --ceiling -1.2 --bass-mono-freq 110 --linear-phase-eq

# Final delivery checks
python tools/antigravity/audio_cli.py qc "./work_audio/polished/mastered" --genre edm
python tools/antigravity/audio_cli.py mono-check "./work_audio/polished/mastered"
python tools/antigravity/audio_cli.py adm-check "./work_audio/polished/mastered" --ceiling -1.2
python tools/antigravity/audio_cli.py codec-preview "./work_audio/polished/mastered/track.wav" -b 128
```

### 2. AI Rock / Band 6-Stem Anti-Slop (`antislop-mix`)

For AI-generated rock/band covers with metallic guitar/cymbal fizz and buried vocals:

```powershell
# Separate 6 stems (vocals, drums, bass, guitar, piano, other)
python tools/antigravity/audio_cli.py prepare "cover.webm" -o "./work_band" --declip auto --trim-tail --stems --demucs-model htdemucs_6s

# List presets or render with active vocal-to-backing (V-B) balance measurement
python tools/antigravity/audio_cli.py antislop-mix --list-presets
python tools/antigravity/audio_cli.py antislop-mix "./work_band" --preset rock-metal --measure-vb

# Master the polished mix
python tools/antigravity/audio_cli.py master "./work_band/polished" --genre metal --linear-phase-eq --deess --bass-mono-freq 100 --ceiling -1.2
```

Available presets:
- `band-analog`: Indie / girl-band live polish (guitar `>9.5 kHz` & cymbal `>13.5 kHz` rolloff, `+2.2 dB` vocal lift, `tanh` warmth).
- `rock-metal`: Vocal-forward heavy rock/metal (`300 Hz` chest warmth, 4x12 guitar `>8.8 kHz` fizz cut, `1.8:1` vocal-to-backing sidechain, `+3.6 dB` vocal lift).

### 3. Distortion-Resistant Pitch & Tempo Shifting (`pitch-tempo`)

```powershell
# Slowed & pitched-down vocal track (preserves vocal formants and stereo coherence)
python tools/antigravity/audio_cli.py pitch-tempo "track.wav" --semitones -2.0 --speed 0.85 --mode vocal

# Instrumental / melody video shift (keeps A/V synchronized using libx264)
python tools/antigravity/audio_cli.py pitch-tempo "clip.mp4" --semitones 2 --speed 1.1 --mode instrumental

# Inspect all 4 modes (vocal, instrumental, drums, smooth)
python tools/antigravity/audio_cli.py pitch-tempo --list-modes
```

---

## Antigravity 2.0 Skills (`.agents/skills/`)

Open this repository as a workspace in Google Antigravity to auto-load the 3 standalone audio skills:

| Skill | Responsibility | Reference |
| :--- | :--- | :--- |
| [`audio-qc-analyzer`](.agents/skills/audio-qc-analyzer/SKILL.md) | 8-check technical QC, LUFS/spectral diagnosis, mono fold-down, AAC ADM & preview | [`qc-checks.md`](.agents/skills/audio-qc-analyzer/references/qc-checks.md) |
| [`audio-mix-engineer`](.agents/skills/audio-mix-engineer/SKILL.md) | De-clipping, Demucs stem prep, 72-genre mix, 6-stem anti-slop, excitation, pitch/tempo | [`mix-presets-guide.md`](.agents/skills/audio-mix-engineer/references/mix-presets-guide.md) |
| [`audio-mastering-engineer`](.agents/skills/audio-mastering-engineer/SKILL.md) | 406-genre mastering, `matchering` reference matching, dynamic repair | [`mastering-targets.md`](.agents/skills/audio-mastering-engineer/references/mastering-targets.md) |

To keep these skills experimental and workspace-scoped, leave them inside `.agents/skills/` rather than registering them globally.

---

## Repository Structure (`antigravity-audio` Additions)

```text
.agents/skills/
  audio-qc-analyzer/         # QC, LUFS, mono-check, adm-check, codec-preview skill
  audio-mix-engineer/        # Prepare, Demucs, mix, antislop-mix, pitch-tempo, excite skill
  audio-mastering-engineer/  # Mastering, ref-master, fix-dynamics skill
tools/antigravity/
  audio_cli.py               # Unified CLI dispatcher (13 subcommands)
  prepare_audio.py           # Format conversion, trim-tail, adeclip, Demucs bridge
  antislop_mix.py            # 6-stem anti-slop EQ, vocal sidechain, tanh warmth
  pitch_tempo.py             # Rubber Band pitch/tempo shifter for audio & video
requirements-audio.txt       # Minimal Python audio dependencies
ANTIGRAVITY.md               # Quick command reference
```

Upstream audio DSP engines used by `audio_cli.py` live in [`tools/mixing/`](tools/mixing/) and [`tools/mastering/`](tools/mastering/).

---

## Syncing Upstream Updates

```powershell
git checkout main
git fetch upstream
git merge --ff-only upstream/main
git push origin main

git checkout antigravity-audio
git merge main
```

---

## License & Attribution

- Original upstream project: [`bitwize-music-studio/claude-ai-music-skills`](https://github.com/bitwize-music-studio/claude-ai-music-skills) ([CC0-1.0](LICENSE))
- Antigravity adaptation & standalone audio CLI extensions on `antigravity-audio` are released under the same [CC0-1.0](LICENSE) license.
