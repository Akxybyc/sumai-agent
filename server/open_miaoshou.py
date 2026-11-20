"""打开妙手ERP，检查登录态。"""
import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "91miaoshou" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.set_viewport_size({"width": 1440, "height": 950})
        pg.goto("https://erp.91miaoshou.com/", wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(5000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 300),
      hasLogin: /登录|login/i.test((document.body.innerText || '').slice(0, 400))
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
