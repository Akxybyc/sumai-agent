"""妙手已登录：进开放平台页，找标准API接口清单。"""
import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "91miaoshou" in x.url)
    pg.bring_to_front()
    # 若还在官网，尝试进 ERP 后台
    if "erp" not in pg.url or pg.url.rstrip("/").endswith("91miaoshou.com"):
        pg.goto("https://erp.91miaoshou.com/erp/", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      menus: Array.from(document.querySelectorAll('a,span,li,div'))
        .filter(e => e.offsetParent)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 8 && /开放|系统管理|采集|刊登|发布|店铺/.test(t))
        .slice(0, 25),
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-300)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
