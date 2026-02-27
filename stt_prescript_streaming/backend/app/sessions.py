from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Dict

import numpy as np

@dataclass
class SessionState:
    session_id: str
    sample_rate: int = 16000
    lock: Lock = field(default_factory=Lock)
    audio: np.ndarray = field(default_factory=lambda: np.zeros((0,), dtype=np.float32))
    is_running: bool = False
    # Incremental transcription bookkeeping
    last_transcribed_samples: int = 0
    last_text: str = ""

    def append_audio(self, chunk: np.ndarray) -> None:
        with self.lock:
            if self.audio.size == 0:
                self.audio = chunk
            else:
                self.audio = np.concatenate([self.audio, chunk])

class SessionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: str, sample_rate: int = 16000) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = SessionState(session_id=session_id, sample_rate=sample_rate)
            return self._sessions[session_id]

    def get(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

STORE = SessionStore()
