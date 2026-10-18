"""錄音、讀取錄音檔、切段。

錄音一律邊錄邊寫入暫存 WAV，長時間會議錄音也不會吃光記憶體。
"""
from __future__ import annotations

import io
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

SAMPLE_RATE = 16000


class Recorder:
    def __init__(self, device: int | None = None):
        self.device = device
        self.level = 0.0  # 0~1，給畫面上的音量條
        self.path: Path | None = None
        self._q: "queue.Queue[np.ndarray | None]" = queue.Queue()
        self._stream = None
        self._writer: threading.Thread | None = None
        self._start = 0.0
        self.frames = 0

    @property
    def recording(self) -> bool:
        return self._stream is not None

    @property
    def elapsed(self) -> float:
        return time.time() - self._start if self.recording else 0.0

    def start(self, path: Path) -> None:
        import sounddevice as sd

        if self.recording:
            return
        self.path = path
        self.frames = 0
        self._q = queue.Queue()
        sfile = sf.SoundFile(
            str(path), mode="w", samplerate=SAMPLE_RATE, channels=1, subtype="PCM_16"
        )

        def writer():
            with sfile:
                while True:
                    block = self._q.get()
                    if block is None:
                        break
                    sfile.write(block)

        self._writer = threading.Thread(target=writer, daemon=True)
        self._writer.start()

        def callback(indata, frames, _time, _status):
            mono = indata[:, 0].copy()
            self.frames += frames
            rms = float(np.sqrt(np.mean(mono**2))) if len(mono) else 0.0
            self.level = min(1.0, rms * 12)
            self._q.put(mono)

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=self.device,
            callback=callback,
            blocksize=1600,  # 0.1 秒
        )
        self._stream.start()
        self._start = time.time()

    def stop(self) -> Path | None:
        if not self.recording:
            return None
        try:
            self._stream.stop()
            self._stream.close()
        finally:
            self._stream = None
            self._q.put(None)
            if self._writer:
                self._writer.join(timeout=5)
            self.level = 0.0
        return self.path

    @property
    def duration(self) -> float:
        return self.frames / SAMPLE_RATE


def new_recording_path(prefix: str = "rec") -> Path:
    from .config import recordings_dir

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return recordings_dir() / f"{prefix}-{stamp}.wav"


def list_input_devices() -> list[tuple[int, str]]:
    import sounddevice as sd

    out = []
    for i, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0:
            out.append((i, d["name"]))
    return out


def load_audio(path: str | Path) -> np.ndarray:
    """讀任何格式（wav/mp3/m4a/mp4…）成 16kHz 單聲道 float32。"""
    p = str(path)
    if p.lower().endswith((".wav", ".flac", ".ogg")):
        data, sr = sf.read(p, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        if sr != SAMPLE_RATE:
            mono = resample(mono, sr, SAMPLE_RATE)
        return mono.astype(np.float32)
    from faster_whisper.audio import decode_audio  # 內含 PyAV，可解 mp3/m4a

    return decode_audio(p, sampling_rate=SAMPLE_RATE)


def resample(x: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to or len(x) == 0:
        return x
    n = int(round(len(x) * sr_to / sr_from))
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def is_silent(x: np.ndarray, threshold: float = 0.006) -> bool:
    if len(x) < SAMPLE_RATE * 0.3:
        return True
    return float(np.sqrt(np.mean(x**2))) < threshold


def split_chunks(x: np.ndarray, max_sec: int = 600, search_sec: int = 20) -> list[np.ndarray]:
    """切成最長 max_sec 秒的段落，盡量切在安靜處，避免把一句話切兩半。"""
    max_len = max_sec * SAMPLE_RATE
    if len(x) <= max_len:
        return [x]
    win = SAMPLE_RATE // 5  # 0.2 秒
    chunks, pos = [], 0
    while len(x) - pos > max_len:
        end = pos + max_len
        lo = max(pos + win, end - search_sec * SAMPLE_RATE)
        seg = x[lo:end]
        n = len(seg) // win
        if n > 0:
            energy = (seg[: n * win].reshape(n, win) ** 2).mean(axis=1)
            cut = lo + int(np.argmin(energy)) * win + win // 2
        else:
            cut = end
        chunks.append(x[pos:cut])
        pos = cut
    chunks.append(x[pos:])
    return chunks


def to_flac_bytes(x: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, x, SAMPLE_RATE, format="FLAC", subtype="PCM_16")
    return buf.getvalue()
