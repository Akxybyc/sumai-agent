import json
import time

from playwright.sync_api import sync_playwright

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
    if "common_collect_box" not in pg.url:
        pg.goto("https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy",
                wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
    pg.bring_to_front()

    hits = []

    def on_resp(r):
        u = r.url
        if any(k in u for k in ("collect", "copy", "task", "goods")):
            try:
                body = r.text()[:200] if r.request.resource_type in ("xhr", "fetch") else ""
            except Exception:
                body = ""
            hits.append({"status": r.status, "method": r.request.method, "url": u[-70:], "body": body})

    pg.on("response", on_resp)

    # 输入
    pg.evaluate(
        """(txt) => {
      const ta = document.querySelector('textarea');
      ta.focus(); ta.value = '';
      ta.dispatchEvent(new Event('input', {bubbles: true}));
      document.execCommand('insertText', false, txt);
    }""",
        PAYLOAD,
    )
    pg.wait_for_timeout(1200)
    print("状态:", pg.evaluate(STATE))

    # 真实鼠标点击按钮坐标（可信事件）
    box = pg.evaluate(
        """() => {
      const b = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '采集并自动认领');
      const r = b.getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2, w: Math.round(r.width)};
    }"""
    )
    print("按钮位置:", box)
    pg.mouse.click(box["x"], box["y"])
    time.sleep(6)

    print("点击后状态:", pg.evaluate(STATE))
    print("网络:", json.dumps(hits[-8:], ensure_ascii=False, indent=1)[:1500])
