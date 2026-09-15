# Voice Shield — Real-Time Voice Cloning Impersonation Defense (Backend)

Backend for **"AI-Powered Real-Time Detection and Prevention of Voice Cloning Impersonation Attacks"** (SIH 2026).

A real-time pipeline that:
1. ingests live microphone audio over WebSocket
2. detects voice spoofing/cloning with **Spectra-AASIST3**
3. transcribes speech with **Groq Whisper large-v3-turbo**
4. scores social-engineering signals with **Groq GPT-OSS**
5. fuses everything into a deterministic, explainable **risk score** with temporal smoothing

---

## Architecture

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, startup/shutdown, HW report
│   ├── api/
│   │   ├── websocket.py           # /ws/audio (and alias /api/v1/stream)
│   │   └── routes.py              # GET /health
│   ├── audio/
│   │   ├── buffer.py              # Rolling mono 16 kHz audio buffer
│   │   └── processing.py          # to_mono, resample, preemphasis, 64.6k window
│   ├── models/
│   │   └── spectra.py             # Spectra-AASIST3 wrapper (load once at startup)
│   ├── services/
│   │   ├── transcription.py       # Groq Whisper ASR
│   │   ├── conversation.py        # Groq GPT-OSS social-engineering analysis (JSON)
│   │   └── risk_engine.py         # Deterministic explainable risk engine + EMA
│   ├── schemas/
│   │   └── messages.py            # Pydantic WebSocket message schemas
│   └── core/
│       ├── config.py              # Environment settings
│       └── logging.py             # Tagged logging ([AUDIO], [SPECTRA], …)
├── tests/                         # pytest suite
├── requirements.txt
├── .env.example
├── run.py
└── README.md
```

### Pipeline diagram

```
Browser mic (Float32 PCM 16 kHz mono, 1 s chunks)
        │  WebSocket binary frames
        ▼
RollingAudioBuffer (max 15 s)
        │
        ├──► prepare_for_spectra (mono → 16 kHz → peak-norm → pre-emphasis 0.97 → 64,600 samples)
        │          ▼
        │    Spectra-AASIST3  ──► raw bona-fide logit + spoof decision
        │
        └──► rolling whisper-transcribed segments ──► transcript ──► GPT-OSS ──► structured JSON signals
        │
        ▼
RiskEngine (voice 0–40, social 0–40, actions 0–20, EMA smoothed)
        ▼
WebSocket JSON events ──► React dashboard
```

---

## Setup

### 1. Python environment

Requires Python 3.12.

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> If you already have a venv with torch/torchaudio/transformers installed (e.g. GPU machine),
> just add the FastAPI stack to it:
> `pip install fastapi "uvicorn[standard]" pydantic-settings httpx pytest pytest-asyncio websockets`

### 2. Environment variables

Copy the template and fill in:

```bash
cp .env.example .env
```

| Variable | Purpose | Example |
|---|---|---|
| `GROQ_API_KEY` | Groq API key for Whisper + GPT-OSS | `gsk_...` |
| `SPECTRA_MODEL_PATH` | Path to local Spectra-AASIST3 dir (`model.py` + `model.safetensors`) | `/home/mnt/spectra-model` |
| `DEVICE` | `cuda` or `cpu` | `cuda` |
| `HOST` | Bind address | `0.0.0.0` |
| `PORT` | Listen port | `8000` |
| `SPECTRA_HOP_SECONDS` | Seconds of NEW audio between Spectra inference runs (default `1.0`) | `1.0` |
| `DEMO_MODE` | `true`/`false` — simulated events only | `false` |

`.env` is git-ignored. Never commit API keys.

### 3. Spectra-AASIST3 model

Two loading options, in priority order:

1. **Local path** — set `SPECTRA_MODEL_PATH` to a directory containing:
   - `model.py` (defines `SpectraAASIST3`, `PyTorchModelHubMixin`)
   - `model.safetensors`

   The wrapper imports the class from that directory and loads weights without
   downloading anything.

2. **HuggingFace Hub** — leave `SPECTRA_MODEL_PATH` empty. The wrapper will load
   `lab260/Spectra-AASIST3` via `from_pretrained` (requires network + HF token
   if the repo is gated). The Wav2Vec2 XLS-R 300M front-end is pulled from
   `facebook/wav2vec2-xls-r-300m`.

Startup report example:

```
PyTorch version: 2.13.0
CUDA available: True
GPU: NVIDIA RTX 5050
Device: cuda
```

### 4. Groq configuration

Get an API key at https://console.groq.com/, set `GROQ_API_KEY` in `.env`.

- **Transcription**: `POST https://api.groq.com/openai/v1/audio/transcriptions`, model `whisper-large-v3-turbo`
- **Conversation analysis**: `POST https://api.groq.com/openai/v1/chat/completions`, model configurable via `GROQ_CHAT_MODEL` (default `openai/gpt-oss-120b`)

> **Model note:** The chat model for conversation analysis is centralized in `app/core/config.py`
> (`GROQ_CHAT_MODEL`, default `openai/gpt-oss-120b`). Set it in `.env` if your Groq account exposes
> a different model ID.

---

## Running the server

```bash
cd backend
python run.py
# or
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
# {"status":"ok","device":"cuda","gpu":"NVIDIA GeForce RTX 5050","spectra_loaded":true,"demo_mode":false}
```

---

## WebSocket protocol

### Endpoint

`ws://localhost:8000/ws/audio`

Also mounted at `ws://localhost:8000/api/v1/stream` (the endpoint referenced by the existing
dashboard's System tab), so the React frontend can connect without modification.

### Client → Server

| Transport | Format | Meaning |
|---|---|---|
| Binary frame | `float32` PCM, mono, **16 kHz** | Audio chunk (the frontend `AudioProcessor` already resamples to 16 kHz mono) |
| Text JSON | `{"type":"ping"}` | Keep-alive; server replies `{"type":"pong"}` |
| Text JSON | `{"type":"start_session"}` | Reset counters/buffer, begin monitoring |
| Text JSON | `{"type":"end_session"}` | Stop monitoring, reset risk engine |

### Server → Client (structured JSON)

All messages are JSON objects with a `type` discriminator. Pydantic schemas live in
`app/schemas/messages.py`.

**`connected`** (sent on connect)
```json
{"type":"connected","message":"Session established","device":"cuda","spectra_loaded":true,"demo_mode":false}
```

**`event`** — feed/recommendation events
```json
{"type":"event","id":"evt-3f2a","timestamp":"00:06","message":"Acoustic spoof indicators detected in voice","severity":"warning","source":"voice"}
```

**`voice_analysis`** — Spectra-AASIST3 result
```json
{"type":"voice_analysis","score":64.2,"is_spoof":true,"confidence":"Spoof Detected","model":"Spectra-AASIST3","raw_bonafide_logit":-2.51}
```
> `raw_bonafide_logit` is the **raw model output** (higher = more bona-fide; the threshold is −1.0625).
> `score` is a display-normalized 0–100 spoof indicator for the UI — it is **not** a probability
> and **not** produced by a calibrated softmax.

**`transcript`** — Whisper ASR
```json
{"type":"transcript","id":"tx-a1f0","timestamp":"00:04","speaker":"caller","text":"Hello, this is officer Davies calling from Federal Trust Bank."}
```

**`conversation_analysis`** — GPT-OSS structured signals (0–1)
```json
{"type":"conversation_analysis","urgency":0.8,"authority_impersonation":0.9,"financial_request":0.5,"credential_request":0.0,"otp_request":0.2,"threat":0.6,"secrecy":0.7,"persuasion":0.75,"repeated_confirmation":0.8,"confidence":0.7,"reasons":["bank impersonation","urgent deadline","don't discuss this"]}
```
> The model analyzes the transcript **in its own language** — it never translates.
> Values are running session maxima: later transcripts can add evidence but can
> never zero out strong signals an earlier line already established.

**`risk_update`** — final fused risk
```json
{"type":"risk_update","risk_score":87,"risk_level":"CRITICAL","voice_score":35.0,"social_score":32.0,"action_score":20.0,"reasons":["Possible synthetic/ cloned voice detected","Caller impersonates authority or institution","Explicit fund transfer instruction detected"],"recommendation":"DO NOT transfer funds or share information. Terminate call immediately and verify independently."}
```

**`error`**
```json
{"type":"error","message":"Voice analysis inference failed","code":"INFERENCE_ERROR"}
```

### Risk model

```
VOICE SPOOF         0–40   (raw bona-fide logit; confirmed spoof ≥ 15, strong spoofs → 40)
SOCIAL ENGINEERING  0–40   (urgency·9 + authority·10 + financial·9 + secrecy·8
                            + persuasion·8 + repeated_confirmation·7 + threat·6)
HIGH-RISK ACTIONS   0–20   (financial·8.5 + credential·6.5 + otp·5)
TOTAL               0–100

0–29   LOW        30–59  MEDIUM        60–79  HIGH        80–100 CRITICAL
```

The three channels are **independent evidence sources**: a human-sounding voice
contributes 0 acoustic points, but the conversation channel can still drive a
confirmed financial-transfer attack into MEDIUM/HIGH on its own. Conversely a
spoofed voice with a completely normal conversation raises the total via the
voice channel alone but never to CRITICAL.

The score is **a risk score, not a probability**. Temporal stability is enforced with an
asymmetric exponential moving average (rise α = 0.8, decay α = 0.2): freshly
detected conversation evidence moves the gauge up promptly, while a single clean
frame cannot collapse an established HIGH/CRITICAL call to LOW.

---

## Demo mode

`DEMO_MODE=true` in `.env`:
- Emits structured events (connected → event) but **never** runs Spectra inference and
  **never** calls Groq.
- It must be *explicitly* enabled; real mode is the default.

The React frontend already has its own client-side demo progression; the backend demo mode is a
separate, explicit facility for server-only demonstrations.

---

## Error handling

The backend survives and emits structured `error` events for:
- malformed audio / unsupported format (bad float32 frames dropped with a log)
- empty or insufficient buffers (analysis skipped until ≥ 64,600 samples)
- Groq API failures / timeouts (skipped, never crashes the socket)
- malformed LLM JSON (falls back to neutral defaults)
- Spectra inference errors (`INFERENCE_ERROR` event)
- WebSocket disconnects (clean session teardown)

## Logging

Tagged stdout logs:
```
[10:00:01] SERVER       INFO   Starting Voice Shield backend
[10:00:02] SPECTRA      INFO   Loading Spectra-AASIST3 on device=cuda
[10:00:08] AUDIO        DEBUG  buffer len=64600 total=132000
[10:00:12] WHISPER      INFO   Transcription: Hello, this is officer Davies...
[10:00:12] CONVERSATION INFO  urgency=0.80 auth=0.90 fin=0.50 cred=0.00 otp=0.20 thr=0.60 secr=0.70 pers=0.75 rep=0.80 reasons=3
[10:00:12] RISK         INFO  Risk: score=87 level=CRITICAL voice=35.0 social=32.0 action=20.0
[10:00:12] LATENCY      INFO  LATENCY session=a1b2c3d4 stage=whisper_finished since_start=4.120s since_prev=1.230s
```

API keys, raw audio and full transcripts are never logged.

---

## Tests

```bash
cd backend
python -m pytest tests/ -v
```

Covered:
- audio buffering (append, trimming, tiling, clear)
- audio processing (mono conversion, resampling, pre-emphasis, 64.6 k window)
- risk calculation & level classification boundaries
- malformed conversation-analysis output handling
- WebSocket message schema validation

---

## Performance notes

- Models are loaded **once** at startup, not per chunk.
- Voice inference runs on the CUDA device over a rolling 15 s window: after the
  first ~4 s window fills, the newest 64,600-sample window is re-scored every
  `SPECTRA_HOP_SECONDS` of NEW audio (default `1.0` = one incoming chunk).
  Raise `SPECTRA_HOP_SECONDS` in `.env` if GPU load makes the 1 s cadence
  unusable.
- Transcription is throttled (cooldown 0.5 s) and only analyses ≥ 1.0 s segments.
  The transcription worker is woken immediately (asyncio event) as soon as a
  speech-bearing chunk has accumulated, rather than waiting on a fixed poll.
- Heavy I/O (Groq) runs in an async background task so the WebSocket receive loop never blocks.
- No audio is written to disk in real mode.

## Troubleshooting

**`ModuleNotFoundError: No module named 'torch'`**
Install the GPU stack: `pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130` (or your CUDA version), then the rest of `requirements.txt`.

**CUDA reports `False` / model runs on CPU**
CUDA must be visible to PyTorch. Check `nvidia-smi`, reinstall the matching wheel, and set
`DEVICE=cuda`. The server always reports the effective device in `/health` and startup logs; it
never pretends CUDA is enabled.

**`RuntimeError: CUDA out of memory`**
The XLS-R 300M front-end plus weights require roughly 5–6 GB. Close other consumers, or force CPU
(`DEVICE=cpu`), or reduce buffer cadence. Loading can also be switched to half precision if needed.

**Spoof results lag / never fire**
Spectra needs ~4.04 s of speech before the first window (64,600 samples) is ready; after
that it re-scores the newest window roughly once per second of new audio
(`SPECTRA_HOP_SECONDS`). The spoof/bona-fide verdict requires 2 consecutive in-agreement
windows, so a switch is reflected within ~2–3 s — not a full 4 s wait per update.
Speak continuously toward the mic. Silence-heavy buffers still run but scores will be less meaningful.

**`from_pretrained failed` falling back**
If `SPECTRA_MODEL_PATH` points at a directory missing either file the loader raises a clear error.
Use the bundled `/home/mnt/spectra-model` layout (`model.py` + `model.safetensors`).

**WebSocket closes immediately**
Check the `connected` JSON event. If `spectra_loaded` is `false`, voice analysis is disabled but
the socket stays open for transcription-driven analysis.

---

## Scope notes / integration status

Works now (verified): `/health`, WebSocket connect handshake, binary audio ingestion, buffering,
mono/resample/pre-emphasis, Spectra load + inference on CUDA, deterministic risk engine with
smoothing, message schema validation, full pytest suite.

Needs backend ↔ frontend integration (not touched — frontend is out of scope per requirements):
- Wire `AudioProcessor.onChunk` output into `WebSocket.send(binaryFrame)` in `LiveAudioInput`.
- Map `BackendPayload` fields in the dashboard from the structured events on this protocol.
- The existing dashboard references `ws://localhost:8000/api/v1/stream`; it is already mounted.

Model names/config reviewed against the published `lab260/Spectra-AASIST3` reference pipeline
(pre-emphasis 0.97, deterministic first-64,600-sample window, score = logit index 1 / bona-fide).