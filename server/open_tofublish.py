import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    clicked = pg.evaluate("""
    () => {
      const el = Array.from(document.querySelectorAll('a, span, li, div'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '待发布')[0];
      if (el) { el.click(); return true; }
      return false;
    }
    """)
    print("clicked 待发布:", clicked)
    pg.wait_for_timeout(5000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      rows: Array.from(document.querySelectorAll('tbody tr'))
        .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 90)).slice(0, 8),
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-350)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1300])
