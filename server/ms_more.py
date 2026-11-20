import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "/welcome" in x.url)
    pg.bring_to_front()
    r = pg.evaluate("""
    () => {
      const el = Array.from(document.querySelectorAll('a,span,li,div'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '更多')[0];
      if (el) { el.click(); return true; }
      return false;
    }
    """)
    print("clicked 更多:", r)
    pg.wait_for_timeout(2000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      items: Array.from(document.querySelectorAll('a,span,li'))
        .filter(e => e.offsetParent)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 10 && /系统|开放|设置|管理/.test(t))
        .slice(0, 20)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
