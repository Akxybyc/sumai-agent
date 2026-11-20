import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_sidebar2.json")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "apifox" in x.url)
    pg.bring_to_front()
    try:
        pg.locator("text=商品").first.click(timeout=4000)
        print("clicked 商品")
    except Exception as e:
        print("click fail", type(e).__name__)
    pg.wait_for_timeout(2500)
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const items = Array.from(document.querySelectorAll('a, li, span, div'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 60);
      return {url: location.href, uniq: Array.from(new Set(items))};
    }
    """)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    u = data["uniq"]
    keys = ("采集", "刊登", "发布", "认领", "商品", "货源", "product", "collect", "publish", "open/")
    hits = [t for t in u if any(k in t.lower() for k in keys)]
    print("total uniq:", len(u), "hits:", len(hits))
    for t in hits[:70]:
        print("-", t[:95])
