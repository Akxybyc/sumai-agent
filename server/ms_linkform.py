import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      return {
        url: location.href,
        inputs: Array.from(document.querySelectorAll('textarea, input')).filter(vis)
          .map(e => ({tag: e.tagName.toLowerCase(), ph: e.placeholder || '', cls: String(e.className).slice(0,40)})).slice(0, 12),
        buttons: Array.from(document.querySelectorAll('button'))
          .filter(vis).map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 20),
        tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-400)
      };
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1600])
