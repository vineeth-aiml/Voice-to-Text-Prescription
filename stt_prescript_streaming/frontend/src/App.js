import React, { useMemo, useRef, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";
const WS_URL = "ws://127.0.0.1:8000/ws/stt";
const AUTO_RX_AFTER_STOP = true;

function pcmEncode(float32Array) {
  const buffer = new ArrayBuffer(float32Array.length * 2);
  const view = new DataView(buffer);
  for (let i = 0; i < float32Array.length; i++) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buffer;
}

function MicIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 14a3 3 0 0 0 3-3V5a3 3 0 0 0-6 0v6a3 3 0 0 0 3 3Zm5-3a5 5 0 0 1-10 0H5a7 7 0 0 0 6 6.92V21h2v-3.08A7 7 0 0 0 19 11h-2Z"
        fill="currentColor"
      />
    </svg>
  );
}

function downloadText(filename, text, mime = "text/plain") {
  const blob = new Blob([text], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function App() {
  const sessionId = useMemo(
    () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now())),
    []
  );

  const [status, setStatus] = useState("Idle");
  const [recording, setRecording] = useState(false);

  // Transcript
  const [text, setText] = useState("");

  // Prescription output
  const [rxJson, setRxJson] = useState(null);
  const [rxMd, setRxMd] = useState("");           // original markdown from backend
  const [rxEditable, setRxEditable] = useState(""); // editable text shown to user
  const [rxLoading, setRxLoading] = useState(false);

  const wsRef = useRef(null);
  const wsReadyRef = useRef(false);

  const audioCtxRef = useRef(null);
  const sourceRef = useRef(null);
  const processorRef = useRef(null);
  const streamRef = useRef(null);

  const ensureWs = () =>
    new Promise((resolve, reject) => {
      const existing = wsRef.current;
      if (existing && existing.readyState === 1 && wsReadyRef.current) return resolve(existing);

      setStatus("Connecting...");
      const ws = new WebSocket(WS_URL);
      ws.binaryType = "arraybuffer";
      wsRef.current = ws;
      wsReadyRef.current = false;

      let done = false;
      const ok = () => { if (!done) { done = true; resolve(ws); } };
      const err = (e) => { if (!done) { done = true; reject(e || new Error("WS failed")); } };

      ws.onopen = () => {
        try {
          ws.send(JSON.stringify({ type: "start", session_id: sessionId, sample_rate: 16000 }));
        } catch {}
      };

      ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data);

          if (msg.type === "started") {
            wsReadyRef.current = true;
            setStatus("Ready");
            ok();
            return;
          }

          if (msg.type === "partial") {
            setText(msg.text || "");
          } else if (msg.type === "commit") {
            const committed = msg.text || "";
            setText(committed);
            setStatus("Done");
            if (AUTO_RX_AFTER_STOP && committed.trim()) generatePrescription(committed);
          } else if (msg.type === "error") {
            setStatus("Error: " + (msg.message || "unknown"));
          }
        } catch {}
      };

      ws.onerror = () => { setStatus("WS Error"); err(new Error("WS error")); };
      ws.onclose = () => { wsReadyRef.current = false; setRecording(false); setStatus("Disconnected"); };

      setTimeout(() => { if (!wsReadyRef.current) err(new Error("WS timeout")); }, 3000);
    });

  const startMic = async () => {
    await ensureWs();

    // clear old rx when new dictation starts
    setRxMd("");
    setRxEditable("");
    setRxJson(null);

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    streamRef.current = stream;

    const AC = window.AudioContext || window.webkitAudioContext;
    const audioCtx = new AC({ sampleRate: 16000 });
    audioCtxRef.current = audioCtx;

    const src = audioCtx.createMediaStreamSource(stream);
    sourceRef.current = src;

    const proc = audioCtx.createScriptProcessor(4096, 1, 1);
    processorRef.current = proc;

    proc.onaudioprocess = (e) => {
      const w = wsRef.current;
      if (!w || w.readyState !== 1) return;
      const input = e.inputBuffer.getChannelData(0);
      w.send(pcmEncode(input));
    };

    src.connect(proc);
    proc.connect(audioCtx.destination);

    setRecording(true);
    setStatus("Listening...");
  };

  const stopMic = async () => {
    setRecording(false);

    const proc = processorRef.current;
    const src = sourceRef.current;
    const ctx = audioCtxRef.current;
    const stream = streamRef.current;

    processorRef.current = null;
    sourceRef.current = null;
    audioCtxRef.current = null;
    streamRef.current = null;

    try { if (proc) { proc.onaudioprocess = null; proc.disconnect(); } } catch {}
    try { if (src) src.disconnect(); } catch {}
    try { if (stream) stream.getTracks().forEach((t) => t.stop()); } catch {}
    try { if (ctx && ctx.state !== "closed") await ctx.close(); } catch {}

    try {
      const ws = wsRef.current;
      if (ws && ws.readyState === 1) ws.send(JSON.stringify({ type: "stop", session_id: sessionId }));
    } catch {}

    setStatus("Finalizing...");
  };

  const toggleDictate = async () => {
    try {
      if (recording) await stopMic();
      else await startMic();
    } catch {
      setRecording(false);
      setStatus("Error");
    }
  };

  const generatePrescription = async (overrideText) => {
    const t = (overrideText ?? text ?? "").trim();
    if (!t || rxLoading) return;

    setRxLoading(true);
    setRxMd("");
    setRxEditable("");
    setRxJson(null);
    setStatus("Generating Prescription...");

    try {
      const res = await fetch(`${API_BASE}/api/prescription`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: t }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Prescription API failed");

      const md = data.markdown || "";
      setRxJson(data.prescription || null);
      setRxMd(md);
      setRxEditable(md); // ✅ editable starts with generated content
      setStatus("Prescription Ready");
    } catch (e) {
      const errText = "Prescription generation failed: " + String(e);
      setRxMd(errText);
      setRxEditable(errText);
      setStatus("Prescription Error");
    } finally {
      setRxLoading(false);
    }
  };

  const copyTranscript = async () => {
    const t = (text || "").trim();
    if (!t) return;
    await navigator.clipboard.writeText(t);
    setStatus("Transcript Copied");
    setTimeout(() => setStatus(recording ? "Listening..." : "Ready"), 800);
  };

  const copyPrescription = async () => {
    const t = (rxEditable || "").trim();
    if (!t) return;
    await navigator.clipboard.writeText(t);
    setStatus("Prescription Copied");
    setTimeout(() => setStatus(recording ? "Listening..." : "Ready"), 800);
  };

  const downloadPrescription = () => {
    const t = (rxEditable || "").trim();
    if (!t) return;
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    downloadText(`prescription-${ts}.txt`, t, "text/plain");
  };

  const downloadPrescriptionJson = () => {
    if (!rxJson) return;
    const ts = new Date().toISOString().replace(/[:.]/g, "-");
    downloadText(`prescription-${ts}.json`, JSON.stringify(rxJson, null, 2), "application/json");
  };

  const resetToGenerated = () => {
    setRxEditable(rxMd || "");
  };

  const clearAll = () => {
    setText("");
    setRxMd("");
    setRxEditable("");
    setRxJson(null);
    setStatus("Ready");
  };

  return (
    <div className="page">
      <header className="header">
        <div>
          <div className="title">Voice Intelligence Prescription</div>
          <div className="subtitle">Tap mic → speak → tap again to stop</div>
        </div>

        <button
          className={"micBtn " + (recording ? "active" : "")}
          onClick={toggleDictate}
          title={recording ? "Stop dictation" : "Start dictation"}
          aria-pressed={recording}
        >
          <MicIcon />
          <span>{recording ? "Stop" : "Dictate"}</span>
        </button>
      </header>

      <div className="card">
        <div className="row">
          <div className="status">{status}</div>
          <div className="actions">
            <button className="btn" onClick={copyTranscript} disabled={!text.trim()}>
              Copy Transcript
            </button>
            <button className="btn" onClick={clearAll} disabled={!text && !rxEditable}>
              Clear
            </button>
          </div>
        </div>

        <textarea
          className="box"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Your dictation will appear here..."
          rows={7}
        />

        <div className="rxRow">
          <button
            className="btn primary"
            onClick={() => generatePrescription()}
            disabled={!text.trim() || rxLoading}
          >
            {rxLoading ? "Generating..." : "Generate Prescription"}
          </button>

          <button className="btn" onClick={copyPrescription} disabled={!rxEditable.trim()}>
            Copy Prescription
          </button>

          <button className="btn" onClick={downloadPrescription} disabled={!rxEditable.trim()}>
            Download TXT
          </button>

          <button className="btn" onClick={downloadPrescriptionJson} disabled={!rxJson}>
            Download JSON
          </button>

          <button className="btn" onClick={resetToGenerated} disabled={!rxMd.trim()}>
            Reset
          </button>
        </div>

        <div className="rxHint">Prescription is editable below. Edit before copy/download.</div>

        <textarea
          className="rxBoxEdit"
          value={rxEditable}
          onChange={(e) => setRxEditable(e.target.value)}
          placeholder="Generated prescription will appear here..."
          rows={12}
        />
      </div>
    </div>
  );
}