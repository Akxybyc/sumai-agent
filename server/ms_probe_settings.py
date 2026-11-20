import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    pg = pages[0]
    if "common_collect_box" not in pg.url:
        pg.goto("https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy",
                wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
    pg.bring_to_front()

    r = pg.evaluate(
        """() => {
      const b = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '采集设置');
      if (!b) return 'no-btn';
      b.click();
      return 'clicked';
    }"""
    )
    print("采集设置:", r)
    pg.wait_for_timeout(3000)
    data = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      const dlg = Array.from(document.querySelectorAll('[class*="drawer"],[class*="dialog"],[class*="modal"]'))
        .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean);
      return {url: location.href, dlg: dlg.slice(0, 3),
              tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-500)};
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1600])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ms_collect_settings.png")
