"""語音辨識：Groq 雲端（預設）與本機 faster-whisper（備援）。"""
from __future__ import annotations

import threading
from typing import Callable

import httpx
import numpy as np

from . import audio, config, textproc

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"

Progress = Callable[[str], None]


class TranscribeError(RuntimeError):
    pass


class SilenceError(TranscribeError):
    def __init__(self):
        super().__init__("麥克風沒有收到聲音：請到設定→一般→「測試麥克風」檢查，或確認 Windows 允許應用程式使用麥克風")


# ---------- Groq ----------
def _groq_chunk(x: np.ndarray, key: str, model: str, prompt: str) -> str:
    files = {"file": ("audio.flac", audio.to_flac_bytes(x), "audio/flac")}
    data = {
        "model": model,
        "language": "zh",
        "response_format": "json",
        "temperature": "0",
        "prompt": prompt,
    }
    for attempt in range(3):
        try:
            r = httpx.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {key}"},
                files=files,
                data=data,
                timeout=180,
            )
        except httpx.HTTPError as e:
            if attempt == 2:
                raise TranscribeError(f"連不上 Groq：{e}") from e
            continue
        if r.status_code == 200:
            return r.json().get("text", "")
        if r.status_code == 401:
            raise TranscribeError("Groq API key 無效，請到設定重新輸入")
        if r.status_code == 429 and attempt < 2:
            import time

            time.sleep(5 * (attempt + 1))
            continue
        raise TranscribeError(f"Groq 回應錯誤 {r.status_code}：{r.text[:200]}")
    raise TranscribeError("Groq 多次重試失敗")


def transcribe_groq(x: np.ndarray, s: config.Settings, progress: Progress | None = None) -> str:
    key = config.get_key("groq")
    if not key:
        raise TranscribeError("尚未設定 Groq API key")
    prompt = textproc.whisper_prompt(s.vocabulary)
    chunks = audio.split_chunks(x)
    parts = []
    for i, c in enumerate(chunks, 1):
        if progress and len(chunks) > 1:
            progress(f"雲端辨識中 {i}/{len(chunks)}")
        parts.append(_groq_chunk(c, key, s.groq_model, prompt))
    return "\n".join(p.strip() for p in parts if p.strip())


# ---------- 本機 ----------
_local_lock = threading.Lock()
_local_model = None
_local_name = None


def _get_local(name: str):
    global _local_model, _local_name
    with _local_lock:
        if _local_model is None or _local_name != name:
            from faster_whisper import WhisperModel

            # 沒有 NVIDIA 顯卡：CPU + int8 量化，速度與準確度的折衷
            _local_model = WhisperModel(
                name,
                device="cpu",
                compute_type="int8",
                download_root=str(config.models_dir()),
            )
            _local_name = name
        return _local_model


def local_model_ready(name: str) -> bool:
    d = config.models_dir()
    return any(d.glob(f"models--Systran--faster-whisper-{name}*"))


def transcribe_local(x: np.ndarray, s: config.Settings, progress: Progress | None = None) -> str:
    if progress and not local_model_ready(s.local_model):
        progress("第一次使用，下載本機模型中…")
    model = _get_local(s.local_model)
    total = len(x) / audio.SAMPLE_RATE
    segments, _info = model.transcribe(
        x,
        language="zh",
        initial_prompt=textproc.whisper_prompt(s.vocabulary),
        vad_filter=True,
        beam_size=5,
        condition_on_previous_text=False,  # 減少長錄音的重複幻聽
    )
    parts = []
    for seg in segments:
        parts.append(seg.text)
        if progress and total > 60:
            progress(f"本機辨識中 {min(99, int(seg.end / total * 100))}%")
    return "".join(parts)


# ---------- 統一入口 ----------
def transcribe(x: np.ndarray, s: config.Settings, progress: Progress | None = None) -> tuple[str, str]:
    """回傳 (繁體文字, 實際使用的引擎)。"""
    if audio.is_silent(x):
        raise SilenceError()
    engine = s.engine
    try:
        if engine == "groq":
            raw = transcribe_groq(x, s, progress)
        else:
            raw = transcribe_local(x, s, progress)
    except TranscribeError:
        # 沒填金鑰是設定問題，直接提示；不要悄悄下載本機模型
        if engine == "groq" and s.fallback_to_local and config.get_key("groq"):
            if progress:
                progress("雲端失敗，改用本機辨識…")
            raw = transcribe_local(x, s, progress)
            engine = "local"
        else:
            raise
    return textproc.postprocess(raw, s.replacements), engine
