"""Agent 记忆层。

两层：
1. 短期：对话历史（data/chat_history.json），保留最近 40 条，重启不丢。
2. 长期：业务事实/偏好（data/memory.json），由模型通过 remember 工具写入，
   每轮以文本形式注入 system prompt（限长，避免膨胀）。
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
HISTORY_FILE = DATA / "chat_history.json"
MEMORY_FILE = DATA / "memory.json"

MAX_HISTORY = 40
MAX_FACTS = 40


# ---------------- 会话历史 ----------------
def load_history() -> list[dict]:
    try:
        if HISTORY_FILE.exists():
            data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            return [m for m in data if m.get("role") in ("user", "assistant")][-MAX_HISTORY:]
    except Exception:
        pass
    return []


def save_history(history: list[dict]) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text(
            json.dumps(history[-MAX_HISTORY:], ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except Exception:
        pass


# ---------------- 长期记忆 ----------------
def load_memory() -> dict:
    try:
        if MEMORY_FILE.exists():
            return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"facts": {}, "notes": []}


def save_memory(mem: dict) -> None:
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        MEMORY_FILE.write_text(json.dumps(mem, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass


def remember(key: str, value: str) -> dict:
    mem = load_memory()
    key = (key or "").strip()[:40]
    value = (value or "").strip()[:300]
    if not key or not value:
        return {"ok": False, "message": "key/value 不能为空"}
    mem["facts"][key] = value
    if len(mem["facts"]) > MAX_FACTS:
        for k in list(mem["facts"])[: len(mem["facts"]) - MAX_FACTS]:
            mem["facts"].pop(k, None)
    save_memory(mem)
    return {"ok": True, "message": f"已记住：{key} = {value}"}


def forget(key: str) -> dict:
    mem = load_memory()
    if key in mem["facts"]:
        mem["facts"].pop(key)
        save_memory(mem)
        return {"ok": True, "message": f"已忘记：{key}"}
    return {"ok": False, "message": f"没有这条记忆：{key}"}


def render_memory() -> str:
    """渲染成注入提示词的短文本（上限约 1200 字）。"""
    mem = load_memory()
    facts = mem.get("facts") or {}
    if not facts:
        return "（暂无长期记忆）"
    lines = [f"- {k}：{v}" for k, v in list(facts.items())[:MAX_FACTS]]
    text = "\n".join(lines)
    return text[:1200]
