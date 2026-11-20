import json
import time

from playwright.sync_api import sync_playwright

LINK = "https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy"
PAYLOAD = "https://detail.1688.com/offer/979658766024.html$$Phone Stand Holder"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    pg = pages[0]
    pg.bring_to_front()
    reqs = []
    pg.on("request", lambda r: reqs.append({"m": r.method, "u": r.url[:110]})
          if r.resource_type in ("xhr", "fetch") else None)

    pg.goto(LINK, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    ta = pg.locator("textarea").first
    ta.click()
    ta.type(PAYLOAD, delay=6)
    pg.wait_for_timeout(1200)
    reqs.clear()

    box = pg.evaluate("""() => {
      const b = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '采集并自动认领');
      const r = b.getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2};
    }""")
    pg.mouse.click(box["x"], box["y"])
    time.sleep(7)
    print("POST/XHR after click:")
    for r in reqs[-12:]:
        print(" ", r["m"], r["u"])
    print("总数:", len(reqs))
