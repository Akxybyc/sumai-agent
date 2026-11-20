import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "goods-wait" in x.url)
    pg.bring_to_front()
    pg.locator(".ivu-select").filter(has_text="Shop1105202845").first.click(timeout=5000)
    pg.wait_for_timeout(1200)
    box = pg.evaluate("""
    () => {
      const els = Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetParent && (e.innerText || '').includes('cn1107939087gdhae'))
        .sort((a, b) => a.innerText.length - b.innerText.length);
      if (!els.length) return null;
      const r = els[0].getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2, t: els[0].innerText.trim().slice(0, 40)};
    }
    """)
    print("target:", box)
    if box:
        pg.mouse.click(box["x"], box["y"])
        pg.wait_for_timeout(5000)
        data = pg.evaluate("""
        () => ({
          store: (document.querySelector('.ivu-select-selected-value') || {}).innerText || '',
          rows: Array.from(document.querySelectorAll('tbody tr'))
            .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 90)).slice(0, 6)
        })
        """)
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
