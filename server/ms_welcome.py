import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if x.url.rstrip("/").endswith("91miaoshou.com/welcome") or "/welcome" in x.url)
    pg.bring_to_front()
    pg.wait_for_timeout(3000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      menus: Array.from(document.querySelectorAll('a,span,li,div'))
        .filter(e => e.offsetParent)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 10 && /开放平台|系统管理|更多|设置/.test(t))
        .slice(0, 20),
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-260)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
