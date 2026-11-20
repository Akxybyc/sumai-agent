import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "91miaoshou" in x.url)
    pg.bring_to_front()
    r = pg.evaluate("""
    () => {
      const el = Array.from(document.querySelectorAll('a,span,li'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '开放平台')[0];
      if (el) { el.click(); return true; }
      return false;
    }
    """)
    print("clicked 开放平台:", r)
    pg.wait_for_timeout(5000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 800),
      buttons: Array.from(document.querySelectorAll('button,a'))
        .filter(e => e.offsetParent)
        .map(e => (e.innerText || '').trim())
        .filter(t => t && t.length <= 12).slice(0, 25)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
