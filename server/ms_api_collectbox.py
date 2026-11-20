import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_collectbox.json")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "apifox" in x.url)
    pg.bring_to_front()
    try:
        pg.locator("text=公共采集箱").first.click(timeout=5000)
        print("clicked 公共采集箱")
    except Exception as e:
        print("click fail", type(e).__name__)
    pg.wait_for_timeout(3000)
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const items = Array.from(document.querySelectorAll('a, li, span, div'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 80);
      // 主内容区标题（接口详情）
      const main = Array.from(document.querySelectorAll('h1,h2,h3,[class*="api-name"],[class*="endpoint"]'))
        .filter(vis).map(e => (e.innerText || '').trim()).slice(0, 10);
      return {url: location.href, main, uniq: Array.from(new Set(items))};
    }
    """)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    u = data["uniq"]
    keys = ("采集", "添加", "写入", "创建", "删除", "列表", "认领", "open/", "接口", "POST", "GET")
    hits = [t for t in u if any(k in t for k in keys)]
    print("main:", data["main"])
    print("hits:")
    for t in hits[:60]:
        print("-", t[:100])
