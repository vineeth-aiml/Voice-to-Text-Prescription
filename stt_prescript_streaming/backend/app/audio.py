import numpy as np

def pcm16_bytes_to_float32_mono(pcm16: bytes) -> np.ndarray:
    """Convert little-endian signed int16 PCM to float32 mono [-1,1]."""
    if not pcm16:
        return np.zeros((0,), dtype=np.float32)
    a = np.frombuffer(pcm16, dtype=np.int16).astype(np.float32)
    return (a / 32768.0).clip(-1.0, 1.0)
