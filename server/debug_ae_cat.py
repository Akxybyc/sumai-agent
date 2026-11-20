import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next(x for x in ctx.pages if "product_publish" in x.url)
    pg.bring_to_front()

    # 1) 参考类目里点含“保温杯”的选项
    opt = pg.locator("li:has-text('保温杯'), label:has-text('保温杯'), div:has-text('>> 保温杯')").last
    try:
        opt.click(timeout=4000)
        pg.wait_for_timeout(3000)
        print("category clicked")
    except Exception as e:
        print("category click failed:", type(e).__name__)

    pg.screenshot(path=str(OUT / "ae_cat.png"))

    # 2) 滚到下面，看供货信息区
    for _ in range(6):
        pg.mouse.wheel(0, 900)
        pg.wait_for_timeout(500)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=str(OUT / "ae_form_rest.png"))

    info = pg.evaluate("""
    () => ({
      text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 2500),
      inputs: Array.from(document.querySelectorAll('input,select,textarea'))
        .filter(e => e.offsetParent).map(e => ({
          tag: e.tagName, type: e.type || '', ph: e.placeholder || '',
          cls: String(e.className || '').slice(0, 60)
        })).slice(0, 60)
    })
    """)
    (OUT / "ae_form_rest.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ok", len(info["inputs"]))
