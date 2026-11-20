"""图片文字预检（用 DeepSeek 视觉模型 deepseek-flash）。

作用：只把「真的有文字」的图送去妙手图片翻译，省额度。
比本地 OCR 稳（本机 onnxruntime 会段错误）。
"""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"

PROMPT = (
    "看这张商品图，判断图中是否含有可读文字（中英文都算）。\n"
    "只输出 JSON，不要解释，格式：{\"has_text\": true/false, \"text\": \"原样文字，最多80字，没有就空\"}"
)


def _cfg() -> dict:
    try:
        s = json.loads((DATA / "settings.json").read_text(encoding="utf-8"))
        return s.get("llm") or {}
    except Exception:
        return {}


def has_text(url: str, timeout: int = 60, cfg: dict | None = None) -> dict:
    cfg = cfg or _cfg()
    key = cfg.get("api_key")
    base = (cfg.get("base_url") or "https://api.deepseek.com").rstrip("/")
    if not key:
        return {"url": url, "has_text": True, "text": "", "engine": "no-key(按有文字处理)"}

    body = {
        "model": cfg.get("vision_model") or "deepseek-flash",
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": url, "detail": "low"}},
            ],
        }],
        "temperature": 0,
    }
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        txt = (data["choices"][0]["message"]["content"] or "").strip()
        s, e = txt.find("{"), txt.rfind("}")
        obj = json.loads(txt[s:e + 1]) if s >= 0 else {}
        return {"url": url, "has_text": bool(obj.get("has_text")),
                "text": str(obj.get("text") or "")[:80], "engine": "deepseek-flash"}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "has_text": True, "text": "",
                "engine": f"error(按有文字处理) {type(e).__name__}"}


def scan(urls: list[str], cfg: dict | None = None) -> dict:
    res = [has_text(u, cfg=cfg) for u in urls]
    with_text = [r for r in res if r["has_text"]]
    return {
        "ok": True,
        "total": len(res),
        "with_text": len(with_text),
        "without_text": len(res) - len(with_text),
        "results": res,
        "engine": res[0]["engine"] if res else "n/a",
    }


if __name__ == "__main__":
    d = json.loads((DATA / "drafts.json").read_text(encoding="utf-8"))
    urls = [u for x in d for u in (x.get("images") or [])][:3]
    r = scan(urls)
    print({k: v for k, v in r.items() if k != "results"})
    for x in r["results"]:
        print(f"  text={x['has_text']} | {x['text'][:40]:42} | {x['url'][-26:]}")
