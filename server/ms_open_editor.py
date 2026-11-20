import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    pg = pages[0]
    pg.bring_to_front()

    # 进采集箱
    if "collect_box" not in pg.url:
        for label in ("速卖通全托管", "速卖通全托管采集箱"):
            ok = pg.evaluate(
                """(l) => {
              const els = Array.from(document.querySelectorAll('a, span, li, div'))
                .filter(e => e.offsetParent && (e.innerText || '').trim() === l)
                .sort((a, b) => a.innerText.length - b.innerText.length);
              if (els.length) { els[0].click(); return true; }
              return false;
            }""",
                label,
            )
            if ok:
                pg.wait_for_timeout(4000)
                break

    # 点第一行「编辑」
    clicked = pg.evaluate(
        """() => {
      const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
      for (const r of rows) {
        const btn = Array.from(r.querySelectorAll('a, span, button, div'))
          .find(e => (e.innerText || '').trim() === '编辑');
        if (btn) { btn.click(); return true; }
      }
      return false;
    }"""
    )
    print("open editor:", clicked, "| url:", pg.url[-40:])
    pg.wait_for_timeout(6000)

    data = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      const heads = Array.from(document.querySelectorAll('h1,h2,h3,h4,[class*="title"],[class*="header"]'))
        .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 20);
      const labels = Array.from(document.querySelectorAll('label, [class*="label"]'))
        .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 24);
      return {
        url: location.href,
        heads: Array.from(new Set(heads)).slice(0, 30),
        labels: Array.from(new Set(labels)).slice(0, 40),
        text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 600)
      };
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=1)[:2200])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ms_edit_page.png")
