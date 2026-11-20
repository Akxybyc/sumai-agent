import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    r = pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button, a'))
        .filter(e => e.offsetParent)
        .find(e => (e.innerText || '').trim() === '去查看');
      if (btn) { btn.click(); return true; }
      return false;
    }
    """)
    print("clicked 去查看:", r)
    pg.wait_for_timeout(6000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      rows: Array.from(document.querySelectorAll('tbody tr'))
        .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 100)).slice(0, 8),
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-300)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1400])
