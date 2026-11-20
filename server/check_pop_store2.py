import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "goods-wait" in x.url)
    pg.bring_to_front()
    sel = pg.locator(".ivu-select").filter(has_text="Shop1105202845").first
    sel.click(timeout=5000)
    pg.wait_for_timeout(1200)
    opt = pg.locator(".ivu-select-dropdown li, .ivu-select-item").filter(has_text="cn1107939087gdhae").first
    txt = opt.inner_text(timeout=5000)
    print("opt:", txt.strip()[:50])
    opt.click()
    pg.wait_for_timeout(5000)
    data = pg.evaluate("""
    () => ({
      store: (document.querySelector('.ivu-select-selected-value') || {}).innerText || '',
      rows: Array.from(document.querySelectorAll('tbody tr'))
        .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 90)).slice(0, 6)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1000])
