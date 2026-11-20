import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    # 找协议勾选框（非 radio）
    cbs = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const cbs = Array.from(document.querySelectorAll('input[type=checkbox]')).filter(vis);
      const info = cbs.map(e => ({checked: e.checked, cls: String(e.className).slice(0, 40)}));
      cbs.forEach(e => { if (!e.checked) e.click(); });
      return info;
    }
    """)
    print("checkboxes:", json.dumps(cbs, ensure_ascii=False))
    pg.wait_for_timeout(1500)
    # 再找采集按钮
    found = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const els = Array.from(document.querySelectorAll('button, [class*="btn"], [class*="button"], a'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && /采集|确定|提交/.test(t)).slice(0, 15);
      return els;
    }
    """)
    print("collect-ish buttons:", found)
