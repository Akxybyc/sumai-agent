"""从速卖通真实爆款标题里提词，替换模板里的属性词/长尾词/流量词。"""

from __future__ import annotations

import math
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import trend_ae  # noqa: E402

STOP = {
    "a", "an", "the", "and", "or", "for", "with", "of", "in", "on", "at", "to", "by", "from",
    "is", "are", "be", "this", "that", "it", "as", "your", "you", "our", "we", "new", "hot",
    "sale", "free", "shipping", "ship", "set", "pcs", "pc", "1", "2", "3", "4", "5", "6",
    "7", "8", "9", "0", "us", "usd", "dollar", "sold", "off", "up", "out", "top", "best",
}
# 明显是品牌/店铺名的高频噪声（可继续补）
BRANDS = {"joyroom", "baseus", "ugreen", "anker", "xiaomi", "apple", "samsung", "huawei",
          "essager", "toocki", "vivo", "oppo", "lenovo", "philips", "nike", "adidas",
          "iphone", "ipad", "ipod", "airpods", "magsafe", "galaxy", "redmi", "honor",
          "oneplus", "realme", "google", "sony", "jbl", "bose", "dyson", "tesla", "bmw"}

CACHE: dict[str, dict] = {}


def _words(title: str) -> list[str]:
    t = re.sub(r"[^A-Za-z0-9 ]", " ", title.lower())
    return [w for w in t.split() if len(w) > 2 and w not in STOP and not w.isdigit()
            and w not in BRANDS]


def extract(core_en: str, limit: int = 20, port: int = 9222, use_cache: bool = True) -> dict:
    """返回 {attr, longtail, flow, top_words, fetched_at, sample_titles}"""
    key = core_en.strip().lower()
    if use_cache and key in CACHE:
        return CACHE[key]

    res = trend_ae.search(core_en, port=port, limit=limit)
    items = res.get("items") or []
    if not items:
        return {"ok": False, "message": "没抓到速卖通数据"}

    freq: Counter = Counter()
    for it in items:
        weight = 1 + math.log10(max(it.get("sold", 0), 1))   # 销量加权
        for w in set(_words(it.get("title", ""))):
            freq[w] += weight

    ranked = [w for w, _ in freq.most_common(40)]
    core_words = set(core_en.lower().split())
    ranked = [w for w in ranked if w not in core_words]

    # 双词组合（相邻词，出现≥2 次才算）
    pairs: Counter = Counter()
    for it in items:
        ws = _words(it.get("title", ""))
        for a, b in zip(ws, ws[1:]):
            if a and b:
                pairs[f"{a} {b}"] += 1
    longtail = [p for p, c in pairs.most_common(10)
                if c >= 2 and not (set(p.split()) & core_words)][:3]

    attr = " ".join(w.capitalize() for w in ranked[:4])
    flow = " ".join(w.capitalize() for w in ranked[4:9])
    lt = " ".join(longtail[0].title().split()) if longtail else " ".join(
        w.capitalize() for w in ranked[9:12])

    out = {
        "ok": True,
        "core": core_en,
        "attr": attr,
        "longtail": lt,
        "flow": flow,
        "top_words": ranked[:20],
        "fetched_at": res.get("fetched_at"),
        "sample_titles": [it.get("title", "")[:70] for it in items[:5]],
        "count": len(items),
    }
    CACHE[key] = out
    return out


if __name__ == "__main__":
    import json

    r = extract("car phone holder")
    print(json.dumps({k: v for k, v in r.items() if k != "sample_titles"}, ensure_ascii=False, indent=1))
    print("样例标题:")
    for t in r.get("sample_titles", []):
        print("  -", t)
