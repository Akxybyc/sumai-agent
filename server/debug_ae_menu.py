import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "csp.aliexpress.com" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.goto("https://csp.aliexpress.com/m_apps/newhome/choice?channelId=2590500",
                wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
    pg.bring_to_front()

    steps = []
    pg.get_by_text("商品管理", exact=True).first.click(timeout=5000)
    pg.wait_for_timeout(1800)
    pg.screenshot(path=str(OUT / "ae_menu.png"))
    steps.append("click 商品管理")

    links = pg.evaluate("""
    () => Array.from(document.querySelectorAll('a, li, div'))
      .map(el => ({text: (el.innerText || '').replace(/\\s+/g, ' ').trim(), href: el.getAttribute('href') || ''}))
      .filter(x => x.text && x.text.length <= 16 && /发布|上架|新品|商品列表|商品/.test(x.text))
      .slice(0, 40)
    """)
    (OUT / "ae_menu_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        pg.get_by_text("发布商品", exact=True).first.click(timeout=4000)
        pg.wait_for_timeout(4000)
        steps.append("click 发布商品")
        pg.screenshot(path=str(OUT / "ae_publish_form.png"))
        info = pg.evaluate("""
        () => ({
          url: location.href,
          title: document.title,
          body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 500),
          inputs: Array.from(document.querySelectorAll('input,select,textarea')).filter(e => e.offsetParent).length
        })
        """)
        (OUT / "ae_publish_form.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        steps.append(f"发布商品 click failed: {type(e).__name__}")

    print("ok", steps, pg.url)
