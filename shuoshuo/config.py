"""設定檔、資料夾位置與 API 金鑰儲存。

設定存在 %APPDATA%\\ShuoShuo\\settings.json；
API 金鑰存在 Windows 認證管理員（keyring），不寫進設定檔。
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import APP_ID

try:
    import keyring  # Windows 認證管理員
except Exception:  # pragma: no cover - 測試環境可能沒有
    keyring = None


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    d = base / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def models_dir() -> Path:
    d = data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def recordings_dir() -> Path:
    d = data_dir() / "recordings"
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Settings:
    # 快捷鍵（pynput 格式）：按一下開始、再按一下結束
    hotkey: str = "<ctrl>+<alt>+<space>"
    # 辨識引擎："groq" 或 "local"
    engine: str = "groq"
    # 雲端失敗時是否自動改用本機
    fallback_to_local: bool = True
    groq_model: str = "whisper-large-v3"
    # 本機 Whisper 模型：tiny / base / small / medium
    local_model: str = "small"
    # 潤飾
    polish_enabled: bool = True
    # 文字 AI 引擎："groq"（免費）、"gemini"（免費額度）、"claude"（付費）
    polish_provider: str = "groq"    # 口述潤飾
    meeting_provider: str = "gemini"  # 會議整理：長文字 Gemini 免費額度較寬；沒金鑰會自動改用 Groq
    # 選的引擎失敗（沒金鑰、額度用完）時，改用其他已填金鑰的引擎
    provider_fallback: bool = True
    groq_chat_model: str = "openai/gpt-oss-120b"
    gemini_model: str = "gemini-2.5-flash"
    claude_model: str = "claude-haiku-5-5"          # 日常口述：快又便宜
    claude_meeting_model: str = "claude-sonnet-5-5"  # 會議整理：品質優先
    current_style: str = "日常"
    # 自訂詞庫：專有名詞（人名、校名、計畫名）
    vocabulary: list[str] = field(default_factory=list)
    # 錯字對照：{"辨識常錯的字": "正確寫法"}
    replacements: dict[str, str] = field(default_factory=dict)
    # 使用者自訂風格：{"風格名": "給 AI 的指示"}
    custom_styles: dict[str, str] = field(default_factory=dict)
    # 麥克風（None = 系統預設）
    input_device: int | None = None
    # 貼上後是否還原原本剪貼簿內容
    restore_clipboard: bool = True
    play_sounds: bool = True

    # ---- 存取 ----
    @classmethod
    def path(cls) -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        p = cls.path()
        if not p.exists():
            s = cls()
            s.save()
            return s
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def save(self) -> None:
        self.path().write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ---- API 金鑰 ----
_SERVICE = APP_ID


def get_key(name: str) -> str:
    """name: 'anthropic'、'groq' 或 'gemini'。環境變數優先（方便開發測試）。"""
    env = {"anthropic": "ANTHROPIC_API_KEY", "groq": "GROQ_API_KEY",
           "gemini": "GEMINI_API_KEY"}.get(name)
    if env and os.environ.get(env):
        return os.environ[env]
    if keyring is None:
        return ""
    try:
        return keyring.get_password(_SERVICE, name) or ""
    except Exception:
        return ""


def set_key(name: str, value: str) -> None:
    if keyring is None:
        raise RuntimeError("此電腦無法使用安全金鑰儲存")
    if value:
        keyring.set_password(_SERVICE, name, value.strip())
    else:
        try:
            keyring.delete_password(_SERVICE, name)
        except Exception:
            pass
