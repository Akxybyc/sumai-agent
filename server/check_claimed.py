import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()

    # 已认领 tab 看看保温杯们
    try:
        pg.get_by_text("已认领", exact=True).first.click(timeout=4000)
        pg.wait_for_timeout(2500)
    except Exception as e:
        print("tab:", type(e).__name__)

    claimed = pg.evaluate("""
    () => ({
      rows: Array.from(document.querySelectorAll('tbody tr'))
        .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 90)).slice(0, 8),
      links: Array.from(document.querySelectorAll('a'))
        .map(a => ({t: (a.innerText || '').trim().slice(0, 16), h: a.href}))
        .filter(x => /待发布|发布/.test(x.t)).slice(0, 8)
    })
    """)
    print(json.dumps(claimed, ensure_ascii=False, indent=2)[:1200])

    # 找"待发布"入口
    nav = pg.evaluate("""
    () => Array.from(document.querySelectorAll('a, span, li'))
      .map(e => (e.innerText || '').trim())
      .filter(t => t && t.length <= 10 && /待发布/.test(t)).slice(0, 10)
    """)
    print("nav 待发布:", nav)
