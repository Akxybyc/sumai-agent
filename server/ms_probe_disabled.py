import json

from playwright.sync_api import sync_playwright

STATE = """() => {
  const btns = Array.from(document.querySelectorAll('button'))
    .filter(e => e.offsetParent && /采集并自动/.test(e.innerText || ''))
    .map(e => ({t: (e.innerText || '').trim(), disabled: e.disabled}));
  const ta = document.querySelector('textarea');
  return {taLen: ta ? (ta.value || '').length : -1, btns};
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()

    ta = pg.locator("textarea").first
    ta.click()
    ta.fill("")
    pg.wait_for_timeout(600)
    print("空输入框:", pg.evaluate(STATE))

    ta.type("http://detail.1688.com/offer/979658766024.html", delay=5)
    pg.wait_for_timeout(1200)
    print("纯链接:", pg.evaluate(STATE))

    # 勾选协议（如果有）
    pg.evaluate(
        """() => {
      document.querySelectorAll('input[type=checkbox]').forEach(c => {
        if (!c.checked && c.offsetParent) c.click();
      });
    }"""
    )
    pg.wait_for_timeout(800)
    print("勾协议后:", pg.evaluate(STATE))
