import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_sidebar.json")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "apifox" in x.url)
    pg.bring_to_front()
    # 找最左侧容器（aside / 树）
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      // apifox 文档左侧树通常是 fixed 宽度较窄的容器
      const cands = Array.from(document.querySelectorAll('div,aside,nav'))
        .filter(e => vis(e) && e.querySelectorAll('a,li').length > 15
                     && e.getBoundingClientRect().width < 420
                     && e.getBoundingClientRect().width > 120);
      const box = cands.sort((a,b)=>b.querySelectorAll('a,li').length - a.querySelectorAll('a,li').length)[0];
      if (!box) return {found: false, texts: []};
      const items = Array.from(box.querySelectorAll('a, li, span'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 60);
      return {found: true, width: Math.round(box.getBoundingClientRect().width), uniq: Array.from(new Set(items))};
    }
    """)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    u = data.get("uniq", [])
    print("found:", data.get("found"), "items:", len(u))
    keys = ("采集", "刊登", "发布", "认领", "商品", "货源", "仓库", "采购", "包裹", "订单")
    hits = [t for t in u if any(k in t for k in keys)]
    for t in hits[:60]:
        print("-", t[:80])
