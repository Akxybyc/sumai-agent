import json

from playwright.sync_api import sync_playwright

JS = "() => ({url: location.href, text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 400), tas: Array.from(document.querySelectorAll('textarea')).filter(e => e.offsetParent).length})"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    print(json.dumps(pg.evaluate(JS), ensure_ascii=False, indent=2))
