import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()

    for label in ("(已选2个平台)", "配置并自动认领"):
        r = pg.evaluate(
            """(label) => {
          const btn = Array.from(document.querySelectorAll('button, a, span, div'))
            .filter(e => e.offsetParent && (e.innerText || '').trim() === label)[0];
          if (btn) { btn.click(); return true; }
          return false;
        }""",
            label,
        )
        print(f"click {label}:", r)
        if r:
            break
    pg.wait_for_timeout(3000)

    data = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      const dlgs = Array.from(document.querySelectorAll('[class*="dialog"],[class*="drawer"],[class*="modal"]'))
        .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean);
      return {dlgs: dlgs.slice(0, 3),
              tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-500)};
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ms_autoclaim_cfg.png")
