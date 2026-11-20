import json
import time

from playwright.sync_api import sync_playwright

LINK = "https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy"
PAYLOAD = "https://detail.1688.com/offer/979658766024.html$$Phone Stand Holder"
STATE = """() => {
  const b = Array.from(document.querySelectorAll('button'))
    .filter(e => e.offsetParent && (e.innerText || '').trim() === '采集并自动认领')[0];
  const ta = document.querySelector('textarea');
  return {taLen: ta ? ta.value.length : -1, disabled: b ? b.disabled : null};
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    pg = pages[0]
    pg.bring_to_front()
    hits = []
    pg.on("response", lambda r: hits.append({"s": r.status, "u": r.url[-60:]})
          if ("collect" in r.url or "copy" in r.url) else None)

    # 全新页面，输入框必为空
    pg.goto(LINK, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    print("刷新后:", pg.evaluate(STATE))

    ta = pg.locator("textarea").first
    ta.click()
    ta.type(PAYLOAD, delay=8)
    pg.wait_for_timeout(1200)
    print("输入后:", pg.evaluate(STATE))

    box = pg.evaluate("""() => {
      const b = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '采集并自动认领');
      if (!b) return null;
      const r = b.getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2, disabled: b.disabled};
    }""")
    print("按钮:", box)
    if box and not box["disabled"]:
        pg.mouse.click(box["x"], box["y"])
        time.sleep(6)
        print("点击后:", pg.evaluate(STATE))
        dlg = pg.evaluate("""() => Array.from(document.querySelectorAll('[class*="dialog"],[class*="message"]'))
          .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean).slice(0,3)""")
        print("弹窗:", dlg)
        print("网络:", json.dumps(hits[-5:], ensure_ascii=False))
