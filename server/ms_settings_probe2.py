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

    # 关掉遗留弹窗
    pg.evaluate("""() => {
      ['我知道了','取消','关闭'].forEach(t => {
        const b = Array.from(document.querySelectorAll('button, span, div'))
          .filter(e => e.offsetParent && (e.innerText || '').trim() === t)[0];
        if (b) b.click();
      });
    }""")
    pg.wait_for_timeout(800)

    pg.evaluate("""() => {
      const b = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '采集设置');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(2500)

    data = pg.evaluate("""() => {
      const vis = e => e.offsetParent !== null;
      const drawer = Array.from(document.querySelectorAll('[class*="drawer"],[class*="dialog"]'))
        .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(t => t.length > 10)[0] || '';
      const checks = Array.from(document.querySelectorAll('input[type=checkbox], input[type=radio]')).filter(vis)
        .map(e => ({type: e.type, checked: e.checked,
                    label: (e.closest('label') ? e.closest('label').innerText : (e.parentElement.innerText || '')).replace(/\\s+/g, ' ').trim().slice(0, 30)}));
      return {drawer: drawer.slice(0, 800), checks: checks.slice(0, 25)};
    }""")
    print(json.dumps(data, ensure_ascii=False, indent=1)[:2000])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ms_collect_settings2.png")
