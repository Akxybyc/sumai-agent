import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data")
LIST_URL = "https://csp.aliexpress.com/m_apps/choiceProductManage/list-manage"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "csp.aliexpress.com" in x.url), None) or ctx.new_page()
    pg.bring_to_front()
    pg.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    pg.screenshot(path=str(OUT / "ae_list.png"))

    before = len(ctx.pages)
    clicked = None
    for text in ("发布商品", "新建商品", "发布"):
        try:
            loc = pg.get_by_text(text, exact=True).first
            if loc.count() > 0:
                loc.click(timeout=4000)
                clicked = text
                pg.wait_for_timeout(5000)
                break
        except Exception:
            continue

    target = pg
    if len(ctx.pages) > before:
        target = ctx.pages[-1]
        target.bring_to_front()
        target.wait_for_timeout(4000)

    info = target.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 600),
      inputCount: Array.from(document.querySelectorAll('input,select,textarea')).filter(e => e.offsetParent).length,
      buttons: Array.from(document.querySelectorAll('button')).filter(e => e.offsetParent)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean).slice(0, 30)
    })
    """)
    info["clicked"] = clicked
    info["pages"] = [x.url for x in ctx.pages]
    (OUT / "ae_publish_form.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    target.screenshot(path=str(OUT / "ae_publish_form.png"))
    print("ok", clicked, info["url"], info["inputCount"])
