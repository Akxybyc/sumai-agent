"""探测 Accio：登录态、可用渠道、是否有上架入口。"""
import json

from playwright.sync_api import sync_playwright

JS = """
() => {
  const t = (document.body.innerText || '').replace(/\\s+/g, ' ');
  const keys = ['速卖通', 'AliExpress', '全托管', '淘宝', '天猫', '抖音', '拼多多', '京东',
                '上架', '发布', '商品', '1688', '绑定店铺', '授权'];
  return {
    url: location.href,
    title: document.title,
    snippet: t.slice(0, 500),
    hits: keys.filter(k => t.includes(k)),
    buttons: Array.from(document.querySelectorAll('button,a,[role="button"]'))
      .filter(e => e.offsetParent)
      .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
      .filter(x => x && x.length < 14).slice(0, 60)
  };
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.set_viewport_size({"width": 1440, "height": 950})
    pg.goto("https://www.accio.com/", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(9000)
    data = None
    for _ in range(3):
        try:
            data = pg.evaluate(JS)
            break
        except Exception:
            pg.wait_for_timeout(3000)
    if data is None:
        data = {"url": pg.url, "title": pg.title(), "err": "evaluate failed"}
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/accio_home.png")
    print(json.dumps(data, ensure_ascii=False))
    pg.close()
