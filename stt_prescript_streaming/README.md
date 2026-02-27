# Streaming Speech-to-Text (Local) — React + FastAPI (Uvicorn)

This project is **true streaming**:

**Speak → send small chunk → transcribe → show text → repeat**

No "record whole file → upload → convert".

## 1) Backend (FastAPI)

### Setup
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# mac/linux:
# source .venv/bin/activate

pip install -r requirements.txt
```

### Run
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/health

## 2) Frontend (React — CRA)

### Setup
```bash
cd frontend
npm install
```

### Run
```bash
npm start
```

Open: http://localhost:3000

## Notes

- Frontend streams **PCM16 mono @ 16kHz** over WebSocket to `ws://127.0.0.1:8000/ws/stt`.
- Model: `small` by default (fast on CPU). For better quality:
  - edit `backend/app/main.py` and set `model_size="medium"` (slower).
