"""速卖通前台趋势采集：抓搜索页商品卡（标题/价格/销量/链接）。

用途：选品决策要有实时依据，而不是只看 1688 销量。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
CACHE = DATA / "ae_trend_cache.json"
TTL = 30 * 60  # 30 分钟内复用，保证时效性


def _page(browser):
    for c in browser.contexts:
        for pg in c.pages:
            if "aliexpress.com" in pg.url:
                return pg
    return None


JS_CARDS = r"""
() => {
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 80 && r.height > 40; };
  const anchors = Array.from(document.querySelectorAll('a')).filter(a => vis(a) && /\/item\/\d+\.html/.test(a.href));
  const map = {};
  for (const a of anchors) {
    const id = (a.href.match(/\/item\/(\d+)\.html/) || [])[1];
    if (!id || map[id]) continue;
    // 向上找包含 sold 的最小容器
    let box = a, text = '';
    for (let i = 0; i < 6 && box.parentElement; i++) {
      box = box.parentElement;
      const t = (box.innerText || '');
      if (/sold/i.test(t) || t.split('\n').length >= 4) { text = t; break; }
    }
    if (!text) text = a.innerText || '';
    const lines = text.split('\n').map(x => x.trim()).filter(Boolean);
    map[id] = { id, href: a.href.split('?')[0], lines: lines.slice(0, 10) };
  }
  return Object.values(map);
}
"""


def parse_price(s: str) -> float:
    m = re.search(r"([\d.]+)", s.replace(",", ""))
    return float(m.group(1)) if m else 0.0


def parse_sold(s: str) -> int:
    s2 = s.replace(",", "").lower()
    m = re.search(r"([\d.]+)\s*([k万]?)", s2)
    if not m:
        return 0
    n = float(m.group(1))
    if m.group(2) in ("k",):
        n *= 1000
    if m.group(2) == "万":
        n *= 10000
    return int(n)


def search(keyword: str, port: int = 9222, limit: int = 20, use_cache: bool = True) -> dict:
    cache = {}
    try:
        if CACHE.exists():
            cache = json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        cache = {}

    key = keyword.strip().lower()
    hit = cache.get(key)
    if use_cache and hit and (time.time() - hit.get("ts", 0) < TTL):
        return {"ok": True, "cached": True, "fetched_at": hit.get("fetched_at"),
                "keyword": keyword, "items": hit.get("items", [])[:limit]}

    from playwright.sync_api import sync_playwright

    url = f"https://www.aliexpress.com/w/wholesale-{keyword.replace(' ', '-')}.html"
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            pg = b.contexts[0].new_page()
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        # 滚两屏触发懒加载
        for _ in range(2):
            pg.mouse.wheel(0, 1400)
            pg.wait_for_timeout(1200)
        cards = pg.evaluate(JS_CARDS)

    items = []
    seen_keys = set()
    for c in cards:
        lines = c["lines"]
        title = next((l for l in lines if len(l) > 12 and not l.startswith("US $") and "sold" not in l.lower()), "")
        # 卡片里常混着 "US $1.09" 优惠文案，取所有价格里最大的合理值
        cands = [parse_price(l) for l in lines if "$" in l]
        cands = [c for c in cands if 0.3 <= c <= 2000]
        price_val = max(cands) if cands else 0.0
        price_line = str(price_val)
        sold_line = next((l for l in lines if "sold" in l.lower()), "")
        if not title:
            continue
        key2 = c.get("id") or title[:60]
        if key2 in seen_keys:
            continue
        seen_keys.add(key2)
        items.append({
            "title": title[:120],
            "price": price_val,
            "sold": parse_sold(sold_line),
            "url": c["href"], "id": c.get("id"),
        })

    items.sort(key=lambda x: x["sold"], reverse=True)
    fetched_at = time.strftime("%Y-%m-%d %H:%M")
    cache[key] = {"ts": time.time(), "fetched_at": fetched_at, "items": items}
    try:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return {"ok": bool(items), "cached": False, "fetched_at": fetched_at,
            "keyword": keyword, "items": items[:limit], "url": url}


if __name__ == "__main__":
    r = search("storage box", limit=8)
    print(json.dumps({k: v for k, v in r.items() if k != "items"}, ensure_ascii=False))
    for it in r.get("items", [])[:8]:
        print(f"  {it['sold']:>6} sold | ${it['price']:>6} | {it['title'][:60]}")
