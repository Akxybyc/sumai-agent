import json

from playwright.sync_api import sync_playwright

STATE = """() => {
  const b = Array.from(document.querySelectorAll('button'))
    .filter(e => e.offsetParent && (e.innerText || '').trim() === '采集并自动认领')[0];
  const ta = document.querySelector('textarea');
  return {taLen: ta.value.length, disabled: b ? b.disabled : null};
}"""
URL = "http://detail.1688.com/offer/979658766024.html"
CASES = [
    ("纯链接", URL),
    ("链接$$英文标题含空格", URL + "$$Vacuum Flask Stainless Steel Travel Mug"),
    ("链接$$中文标题", URL + "$$保温杯测试标题"),
]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    # 先关掉可能的弹窗
    pg.evaluate("""
    () => {
      ['我知道了', '取消', '关闭'].forEach((t) => {
        const b = Array.from(document.querySelectorAll('button, a, span, div'))
          .filter(e => e.offsetParent && (e.innerText || '').trim() === t)[0];
        if (b) b.click();
      });
    }
    """)
    pg.wait_for_timeout(800)
    ta = pg.locator("textarea").first
    for name, text in CASES:
        ta.click()
        ta.fill("")
        pg.wait_for_timeout(300)
        ta.type(text, delay=4)
        pg.wait_for_timeout(1000)
        print(f"{name:22} -> {pg.evaluate(STATE)}")
