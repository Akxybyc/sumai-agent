import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
drafts = json.loads((DATA / "drafts.json").read_text(encoding="utf-8"))
d = drafts[0]
payload = f"{d['source_url']}$${d['title_en'][:110]}"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()

    # 检查 shadow DOM 数量
    shadow = pg.evaluate(
        """() => {
      let n = 0;
      const walk = (root) => {
        for (const e of root.querySelectorAll('*')) {
          if (e.shadowRoot) { n++; walk(e.shadowRoot); }
        }
      };
      walk(document);
      return n;
    }"""
    )
    print("shadow roots:", shadow)

    # Playwright 定位器（穿透 shadow DOM）
    ta = pg.locator("textarea").first
    ta.click()
    ta.fill("")
    ta.type(payload, delay=5)
    pg.wait_for_timeout(1500)

    for name in ("开始采集", "立即采集", "一键采集", "采集"):
        loc = pg.get_by_text(name, exact=True)
        cnt = loc.count()
        if cnt:
            print(f"'{name}' x{cnt}")
            for i in range(cnt):
                el = loc.nth(i)
                try:
                    if el.is_visible():
                        print("  visible:", i, el.inner_text()[:20])
                except Exception:
                    pass
