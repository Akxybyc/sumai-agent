import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "91miaoshou" in x.url and "agent" not in x.url and "welcome" not in x.url), None)
    if pg is None:
        pg = ctx.new_page()
    if "91miaoshou" not in pg.url or "agent.html" in pg.url:
        pg.goto("https://erp.91miaoshou.com/picture/index", wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(3000)
    r = pg.evaluate("""
    () => {
      const el = Array.from(document.querySelectorAll('li,span,div,a'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '产品')[0];
      if (el) { el.click(); return true; }
      return false;
    }
    """)
    print("clicked 产品:", r)
    pg.wait_for_timeout(2000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      items: Array.from(document.querySelectorAll('a,span,li'))
        .filter(e => e.offsetParent)
        .map(e => ({t: (e.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 12), h: (e.href || '').slice(0, 80)}))
        .filter(x => x.t && /采集|刊登|发布|商品|产品/.test(x.t))
        .slice(0, 30)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1800])
