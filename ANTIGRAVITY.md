# Antigravity Audio Skills & Standalone CLI (`antigravity-audio`)

This branch adapts the audio-processing engine of [`bitwize-music-studio/claude-ai-music-skills`](https://github.com/bitwize-music-studio/claude-ai-music-skills) (CC0-1.0) for **Google Antigravity 2.0** and **general-purpose local audio** (YouTube downloads, Suno exports, or any `.wav`/`.mp3`/`.flac`/`.m4a`/`.webm` file) **without requiring Suno MCP or Claude Code plugins**.

Upstream files in `skills/`, `tools/mixing/`, `tools/mastering/`, and `servers/` are left untouched so `upstream/main` updates merge cleanly.

---

## What Was Added

- `requirements-audio.txt` — Audio-only Python dependencies (drops Playwright, PostgreSQL, AWS S3, and MCP server extras).
- `tools/antigravity/prepare_audio.py` — Universal input bridge: converts audio to 44.1 kHz stereo WAV, optionally trims trailing silence (`--trim-tail`), repairs digital clipping via FFmpeg `adeclip` (`--declip auto`), and optionally runs local **Demucs** (`--stems`) into `stems/<track>/`.
- `tools/antigravity/audio_cli.py` — Unified CLI dispatcher (`prepare`, `qc`, `analyze`, `mix`, `excite`, `master`, `ref-master`, `fix-dynamics`, `mono-check`, `adm-check`, `codec-preview`).
- `.agents/skills/` — 3 lean Antigravity 2.0 skills:
  - [`audio-qc-analyzer`](.agents/skills/audio-qc-analyzer/SKILL.md) — 8-check technical QC, LUFS/dynamics analysis, mono fold-down, AAC codec preview
  - [`audio-mix-engineer`](.agents/skills/audio-mix-engineer/SKILL.md) — De-clip + Demucs bridge + per-stem/full-mix cleanup & EQ
  - [`audio-mastering-engineer`](.agents/skills/audio-mastering-engineer/SKILL.md) — Genre mastering (406 presets), reference matching (`matchering`), dynamics repair

---

## Quick Setup (오디오 전용 빠른 설치)

```powershell
# 1. Python 3.11+ 환경에 오디오 필수 패키지 설치
pip install -r requirements-audio.txt

# 2. (선택) 로컬 AI 스템 분리(보컬/드럼/베이스/기타) 사용 시 Demucs 설치
pip install demucs

# 3. 시스템 필수 도구: ffmpeg & ffprobe 가 PATH 에 있어야 합니다.
ffmpeg -version
```

---

## Standalone Audio Workflow (일반 음원 처리 파이프라인)

```powershell
# 1. 입력 변환 + 자동 디클리핑 + 무음 정리 + Demucs 4-스템 분리
python tools/antigravity/audio_cli.py prepare "track.mp3" -o "./work_audio" --declip auto --trim-tail --stems

# 2. 기술 QC 및 음량(LUFS) 진단
python tools/antigravity/audio_cli.py qc "./work_audio/declipped" --genre edm
python tools/antigravity/audio_cli.py analyze "./work_audio/declipped"

# 3. 스템 기반 믹싱/복원 (또는 --full-mix 모드)
python tools/antigravity/audio_cli.py mix "./work_audio" --genre edm --dry-run
python tools/antigravity/audio_cli.py mix "./work_audio" --genre edm

# 4. 마스터링 (장르 프리셋 또는 레퍼런스 트랙 매칭)
python tools/antigravity/audio_cli.py master "./work_audio/polished" --genre edm --target-lufs -10.5 --ceiling -1.0
# 또는 레퍼런스 음원 기반:
# python tools/antigravity/audio_cli.py ref-master --reference "ref.wav" --target "./work_audio/polished/track.wav" --output-dir "./work_audio/polished/mastered"

# 5. 최종 검증 (QC + 모노 호환성 + AAC 인터샘플 ADM 검증 + 128k AAC 미리듣기)
python tools/antigravity/audio_cli.py qc "./work_audio/polished/mastered" --genre edm
python tools/antigravity/audio_cli.py mono-check "./work_audio/polished/mastered"
python tools/antigravity/audio_cli.py adm-check "./work_audio/polished/mastered" --ceiling -1.0
python tools/antigravity/audio_cli.py codec-preview "./work_audio/polished/mastered/track.wav" -b 128

# (선택) 어둡거나 답답한 스템에 상단 배음만 보강하려면:
# python tools/antigravity/audio_cli.py excite "./work_audio/stems/track/vocals.wav" --amount-db 2.0
```

---

## Using Skills in Antigravity

- **Workspace-local**: Open this repository as your Antigravity workspace — `.agents/skills/*` is discovered automatically.
- **Global Personal Library**: Copy `.agents/skills/audio-*` into your personal `skills_library` bundle (e.g. `C:\Users\MSI\.gemini\antigravity\skills_library\bundle-utilities\`) and run `validate_skill.py --sync-index`, or attach them selectively via `.agents/skills.json`.

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
