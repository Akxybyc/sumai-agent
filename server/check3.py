from playwright.sync_api import sync_playwright

JS = """
() => Array.from(document.querySelectorAll('input')).filter(e => e.offsetParent && e.value)
  .map(e => ({v: e.value.slice(0, 40), ph: e.placeholder || ''}))
  .filter(x => /20\\.93|3666|ZNZ|0\\.45|^8$|^24$/.test(x.v))
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if "product_publish" in x.url)
    pg.bring_to_front()
    for r in pg.evaluate(JS):
        print(r)
