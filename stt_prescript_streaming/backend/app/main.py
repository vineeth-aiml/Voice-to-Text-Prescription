import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.llm_prescription import RxRequest, RxResponse
from app.llm_prescription_http import rx_from_text, rx_markdown

from .sessions import STORE
from .stt import WhisperTranscriber
from .audio import pcm16_bytes_to_float32_mono

app = FastAPI(title="Local Streaming STT (Whisper) + Rx via llama-server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TRANSCRIBER = WhisperTranscriber(
    model_size="medium",
    device="cpu",
    compute_type="int8",
)

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/prescription", response_model=RxResponse)
def generate_prescription(req: RxRequest):
    try:
        rx = rx_from_text(req.text)
        md = rx_markdown(rx)
        return RxResponse(prescription=rx, markdown=md)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Prescription generation failed: {e}")

@app.websocket("/ws/stt")
async def ws_stt(ws: WebSocket):
    await ws.accept()
    session = None

    try:
        while True:
            msg = await ws.receive()

            if "text" in msg and msg["text"]:
                try:
                    obj = json.loads(msg["text"])
                except Exception:
                    await ws.send_text(json.dumps({"type": "error", "message": "Invalid JSON control message"}))
                    continue

                t = obj.get("type")

                if t == "start":
                    sid = obj.get("session_id")
                    if not sid:
                        await ws.send_text(json.dumps({"type": "error", "message": "Missing session_id"}))
                        continue

                    sr = int(obj.get("sample_rate", 16000))
                    if sr != 16000:
                        await ws.send_text(json.dumps({
                            "type": "error",
                            "message": f"Backend expects 16000 Hz, got {sr}. Set AudioContext sampleRate=16000."
                        }))
                        continue

                    session = STORE.get_or_create(sid, sample_rate=sr)
                    session.is_running = True
                    await ws.send_text(json.dumps({"type": "started", "session_id": sid}))
                    continue

                if t == "stop":
                    if session:
                        session.is_running = False
                        final_text = TRANSCRIBER.transcribe_full(session)
                        if final_text:
                            await ws.send_text(json.dumps({"type": "commit", "text": final_text, "final": True}))
                    await ws.send_text(json.dumps({"type": "stopped"}))
                    break

            if "bytes" in msg and msg["bytes"]:
                if not session or not session.is_running:
                    continue

                chunk = pcm16_bytes_to_float32_mono(msg["bytes"])
                session.append_audio(chunk)

                out = TRANSCRIBER.transcribe_incremental(session)
                if out:
                    await ws.send_text(json.dumps({"type": "partial", "text": out}))

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.send_text(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass
    finally:
        if session:
            session.is_running = False