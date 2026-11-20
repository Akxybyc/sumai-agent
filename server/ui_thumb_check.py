import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "127.0.0.1:8000" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.goto("http://127.0.0.1:8000", wait_until="domcontentloaded")
    else:
        pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    pg.evaluate("""() => {
      const b = Array.from(document.querySelectorAll('[data-view="review"]'))[0];
      if (b) b.click();
    }""")
    pg.wait_for_timeout(3000)

    data = pg.evaluate("""() => {
      const imgs = Array.from(document.querySelectorAll('.dthumb img'));
      return {
        cards: document.querySelectorAll('.dcard').length,
        imgs: imgs.length,
        loaded: imgs.filter(i => i.complete && i.naturalWidth > 0).length,
        sample: imgs.slice(0,2).map(i => ({src: i.src.slice(-50), w: i.naturalWidth})),
        placeholders: document.querySelectorAll('.dthumb span').length
      };
    }""")
    print(json.dumps(data, ensure_ascii=False, indent=1))
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ui_thumbs_check.png")
