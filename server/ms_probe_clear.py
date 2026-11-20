import json

from playwright.sync_api import sync_playwright

PAYLOAD = "https://detail.1688.com/offer/979658766024.html$$Phone Stand Holder"
STATE = """() => {
  const b = Array.from(document.querySelectorAll('button'))
    .filter(e => e.offsetParent && (e.innerText || '').trim() === '采集并自动认领')[0];
  const ta = document.querySelector('textarea');
  return {taLen: ta ? ta.value.length : -1, val: ta ? ta.value.slice(0, 60) : '',
          disabled: b ? b.disabled : null};
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    if not pages:
        raise SystemExit("没有妙手页面")
    pg = pages[0]
    if "common_collect_box" not in pg.url:
        pg.goto("https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy",
                wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
    pg.bring_to_front()

    print("起始:", pg.evaluate(STATE))

    # JS 强制清空（触发 Vue 的 input）
    pg.evaluate(
        """() => {
      const ta = document.querySelector('textarea');
      ta.focus();
      ta.value = '';
      ta.dispatchEvent(new Event('input', {bubbles: true}));
      ta.dispatchEvent(new Event('change', {bubbles: true}));
    }"""
    )
    pg.wait_for_timeout(600)
    print("清空后:", pg.evaluate(STATE))

    # 用 insertText 写入，确保 v-model 同步
    pg.evaluate(
        """(txt) => {
      const ta = document.querySelector('textarea');
      ta.focus();
      document.execCommand('insertText', false, txt);
    }""",
        PAYLOAD,
    )
    pg.wait_for_timeout(1000)
    print("写入后:", pg.evaluate(STATE))

    if pg.evaluate(STATE)["disabled"] is False:
        pg.evaluate(
            """() => {
          const b = Array.from(document.querySelectorAll('button'))
            .find(e => (e.innerText || '').trim() === '采集并自动认领');
          b.click();
        }"""
        )
        print("已点击")
        pg.wait_for_timeout(4000)
        print("点击后:", pg.evaluate("""() => {
          const d = Array.from(document.querySelectorAll('[class*="dialog"],[class*="modal"]'))
            .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).slice(0, 2);
          const ta = document.querySelector('textarea');
          return {dlg: d, taLen: ta.value.length};
        }"""))
