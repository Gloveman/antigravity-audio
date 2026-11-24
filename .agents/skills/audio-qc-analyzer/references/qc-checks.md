# QC Checks & Analysis Reference

## Technical QC Checks (`qc_tracks.py`)

Invoke via `python tools/antigravity/audio_cli.py qc <wav_dir> [--checks <list>] [--genre <genre>] [-j 0]`:

| Check | What It Inspects | Typical Failure Condition |
| :--- | :--- | :--- |
| `format` | Container, sample rate, bit depth, channels | Non-WAV, non-standard sample rate, unsupported subtype, >2 channels |
| `mono` | Left/Right identity or mono track | 1-channel WAV (`WARN`, fixable to stereo) |
| `phase` | L/R stereo correlation | Negative correlation causing phase cancellation |
| `clipping` | Consecutive full-scale flat-top samples | Digital clipping distortion |
| `truepeak` | Oversampled inter-sample true peak | Exceeds `-1.0 dBTP` ceiling |
| `clicks` | Transient impulse spikes (genre-aware via `--genre`) | Unwanted pops/clicks; pass `--genre edm` etc. for sharp-transient genres |
| `silence` | Leading/trailing silence duration | Excessive dead silence tail (fixable with `prepare --trim-tail`) |
| `spectral` | Band energy & spectral balance anomalies | Extreme harshness, sub rumble, or missing bands |

## Loudness & Dynamics Analysis (`analyze_tracks.py`)

Invoke via `python tools/antigravity/audio_cli.py analyze <wav_dir> [-j 0]`:
- Integrated LUFS vs `-14.0 LUFS` streaming baseline
- Sample / True Peak (`dBFS`)
- Short-term (`3s`) and momentary (`400ms`) LUFS dynamics spread

## Mono Fold-Down (`mono-check`), ADM (`adm-check`), & Codec Preview (`codec-preview`)

- `mono-check` compares stereo vs `(L+R)/2` across 7 bands (`sub_bass` 20–60 Hz through `air` 12–20 kHz) plus `1–4 kHz` vocal RMS and stereo correlation (`warn < 0.3`, band drop `fail < -6.0 dB`).
- `adm-check <wav_or_dir> [-b 256] [--ceiling -1.0] [--encoder aac|afconvert|libfdk_aac]` tests Apple Digital Masters compliance by encoding to AAC, decoding back to float32 PCM, and flagging any inter-sample overshoot above `--ceiling`.
- `codec-preview <track.wav> [-o out.aac.m4a] [-b 128]` renders a 128 kbps AAC file via FFmpeg to audition high-frequency smearing or post-encoding overshoot before distribution.
