"""文字前處理：簡轉繁、錯字對照、詞庫提示。純函式，方便測試。"""
from __future__ import annotations

import re

try:
    from opencc import OpenCC

    _cc = OpenCC("s2twp")  # 簡體 → 臺灣正體（含慣用詞）
except Exception:  # pragma: no cover
    _cc = None


def to_traditional(text: str) -> str:
    if not text or _cc is None:
        return text
    return _cc.convert(text)


def apply_replacements(text: str, rules: dict[str, str]) -> str:
    """一次掃過、長詞優先；替換後的文字不會再被其他規則改到。"""
    keys = sorted((k for k in rules if k), key=len, reverse=True)
    if not keys:
        return text
    pattern = re.compile("|".join(re.escape(k) for k in keys))
    return pattern.sub(lambda m: rules[m.group(0)], text)


def whisper_prompt(vocabulary: list[str]) -> str:
    """給 Whisper 的提示：讓它偏向繁體與這些專有名詞。Whisper 提示上限約 224 tokens。"""
    base = "以下是繁體中文的口述內容，使用臺灣用語與全形標點。"
    if not vocabulary:
        return base
    terms = "、".join(v.strip() for v in vocabulary if v.strip())
    return (base + "可能出現的詞：" + terms + "。")[:200]


def clean_transcript(text: str) -> str:
    """去掉 Whisper 常見的幻聽字句與多餘空白。"""
    junk = [
        r"請不吝點贊.*", r"字幕由.*提供", r"謝謝觀看[。！]?$", r"訂閱.*頻道.*",
        r"以下是繁體中文的口述內容.*?。",
    ]
    for pat in junk:
        text = re.sub(pat, "", text)
    text = re.sub(r"[ \t]+", " ", text)
    # 中文字之間的空白移除
    text = re.sub(r"(?<=[一-鿿，。！？、]) (?=[一-鿿])", "", text)
    return text.strip()


def postprocess(text: str, rules: dict[str, str]) -> str:
    return apply_replacements(clean_transcript(to_traditional(text)), rules)
