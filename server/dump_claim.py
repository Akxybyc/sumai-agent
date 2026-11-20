import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    data = pg.evaluate("""
    () => {
      const t = (document.body.innerText || '').replace(/\\s+/g, ' ');
      const vis = (e) => e.offsetParent !== null;
      return {
        bodyTail: t.slice(-900),
        buttons: Array.from(document.querySelectorAll('button')).filter(vis)
          .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean).slice(0, 30),
        inputs: Array.from(document.querySelectorAll('input')).filter(vis)
          .map(e => e.placeholder || e.value || '').filter(Boolean).slice(0, 20)
      };
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
