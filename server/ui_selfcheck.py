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
    errs = []
    pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.wait_for_timeout(4000)

    # 切到审核台
    pg.evaluate("""() => {
      const b = Array.from(document.querySelectorAll('[data-view="review"]'))[0];
      if (b) b.click();
    }""")
    pg.wait_for_timeout(2500)

    data = pg.evaluate("""() => ({
      cards: document.querySelectorAll('.dcard').length,
      picks: document.querySelectorAll('[data-pick]').length,
      pager: !!document.querySelector('.pager'),
      pagerInfo: (document.querySelector('.pager-info') || {}).innerText || '',
      selAll: !!document.querySelector('#selAllBtn'),
      delSel: !!document.querySelector('#delSelBtn'),
      thumbs: document.querySelectorAll('.dthumb img').length,
      srcLinks: document.querySelectorAll('.dsrc a').length,
      logsBtn: !!document.querySelector('#logsBtn')
    })""")
    print(json.dumps(data, ensure_ascii=False, indent=1))
    print("console errors:", errs[:5])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ui_review_check.png", full_page=False)
