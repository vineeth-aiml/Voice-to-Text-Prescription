from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from faster_whisper import WhisperModel

from .sessions import SessionState

@dataclass
class WhisperTranscriber:
    model_size: str = "small"
    device: str = "cpu"
    compute_type: str = "int8"

    def __post_init__(self):
        # Load once
        self.model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)

    def _run(self, audio_f32: np.ndarray) -> str:
        if audio_f32.size == 0:
            return ""
        # faster-whisper accepts numpy float32 at 16kHz
        segments, _info = self.model.transcribe(
            audio_f32,
            language=None,          # auto
            vad_filter=True,        # helps on noisy mics
            beam_size=3,
            temperature=0.0,
        )
        text = " ".join((seg.text or "").strip() for seg in segments).strip()
        return " ".join(text.split())

    def transcribe_incremental(self, session: SessionState, min_new_ms: int = 900) -> str:
        """Re-transcribes a sliding window when enough new audio arrives.
        Returns partial text (best effort).
        """
        with session.lock:
            sr = session.sample_rate
            total = session.audio.size
            new_samples = total - session.last_transcribed_samples
            if new_samples <= int(sr * (min_new_ms / 1000.0)):
                return ""
            # Sliding window: last 25 seconds max (keeps CPU ok)
            window_s = 25
            start = max(0, total - sr * window_s)
            audio = session.audio[start:total].copy()
            session.last_transcribed_samples = total

        text = self._run(audio)
        # Light de-dup: if model repeats earlier text, keep longer one
        if not text:
            return ""
        with session.lock:
            if len(text) >= len(session.last_text):
                session.last_text = text
            return session.last_text

    def transcribe_full(self, session: SessionState) -> str:
        with session.lock:
            audio = session.audio.copy()
        return self._run(audio)
