import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    box = pg.evaluate("""
    () => {
      const els = Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetParent && /1688\\s*未授权/.test(e.innerText || ''))
        .sort((a, b) => a.innerText.length - b.innerText.length);
      if (!els.length) return null;
      const r = els[0].getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2, t: els[0].innerText.trim().slice(0, 30)};
    }
    """)
    print("target:", box)
    if box:
        pg.mouse.click(box["x"], box["y"])
        pg.wait_for_timeout(4000)
    pages = [(x.url[:80], x.title()[:30]) for x in b.contexts[0].pages]
    print(json.dumps(pages, ensure_ascii=False, indent=1))
    dlg = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const mods = Array.from(document.querySelectorAll('[class*="dialog"],[class*="modal"],[class*="Dialog"]')).filter(vis);
      return mods.map(m => (m.innerText || '').replace(/\\s+/g, ' ').slice(0, 200));
    }
    """)
    print(json.dumps(dlg, ensure_ascii=False, indent=1)[:800])
