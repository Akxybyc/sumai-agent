import json
import time

from playwright.sync_api import sync_playwright

LINK = "https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy"
PAYLOAD = "http://detail.1688.com/offer/979658766024.html$$Phone Stand Test Enter Submit"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "91miaoshou" in x.url)
    if "common_collect_box" not in pg.url:
        pg.goto(LINK, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
    pg.bring_to_front()

    # 打印按钮的 disabled 状态与标签
    info = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      return Array.from(document.querySelectorAll('button'))
        .filter(vis)
        .map(e => ({t: (e.innerText || '').trim(), disabled: e.disabled,
                    cls: String(e.className).slice(0, 45)}));
    }"""
    )
    print("buttons:", json.dumps(info, ensure_ascii=False)[:700])

    ta = pg.locator("textarea").first
    ta.click()
    ta.fill("")
    ta.type(PAYLOAD, delay=8)
    pg.wait_for_timeout(800)
    print("taLen:", pg.evaluate("() => document.querySelector('textarea').value.length"))

    # 实验 A：回车
    ta.press("Enter")
    pg.wait_for_timeout(3000)
    a = pg.evaluate(
        """() => {
      const d = Array.from(document.querySelectorAll('[class*="dialog"],[class*="modal"]'))
        .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).slice(0, 2);
      const ta = document.querySelector('textarea');
      return {dlg: d, taLen: ta ? ta.value.length : -1};
    }"""
    )
    print("A 回车后:", json.dumps(a, ensure_ascii=False)[:400])

    time.sleep(2)
    # 实验 B：JS 直接点击按钮（绕过 disabled 判定）
    bres = pg.evaluate(
        """() => {
      const btn = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '采集并自动认领');
      if (!btn) return 'no-btn';
      btn.disabled = false;
      btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
      return 'dispatched';
    }"""
    )
    print("B 派发:", bres)
    pg.wait_for_timeout(3500)
    b2 = pg.evaluate(
        """() => {
      const d = Array.from(document.querySelectorAll('[class*="dialog"],[class*="modal"]'))
        .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).slice(0, 2);
      const ta = document.querySelector('textarea');
      return {dlg: d, taLen: ta ? ta.value.length : -1};
    }"""
    )
    print("B 后:", json.dumps(b2, ensure_ascii=False)[:400])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ms_probe_submit.png")
