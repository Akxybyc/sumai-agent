import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
drafts = json.loads((DATA / "drafts.json").read_text(encoding="utf-8"))
d = drafts[0]
payload = f"{d['source_url']}$${d['title_en'][:110]}"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    ta = pg.locator("textarea").first
    ta.click(timeout=5000)
    # 用 execCommand insertText 触发 Vue 响应
    pg.evaluate(
        """(txt) => {
      document.activeElement.dispatchEvent(new Event('focus'));
      document.execCommand('insertText', false, txt);
    }""",
        payload,
    )
    time.sleep(1.5)
    n = pg.evaluate("() => (document.querySelector('textarea')||{}).value ? document.querySelector('textarea').value.length : 0")
    print("taLen:", n)
    # 等按钮出现（轮询 6 次）
    for i in range(6):
        btns = pg.evaluate(
            """() => {
        const vis = e => e.offsetParent !== null;
        return Array.from(document.querySelectorAll('button, [class*="btn"], [class*="button"], a, div, span'))
          .filter(vis)
          .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
          .filter(t => /^(采集|开始采集|立即采集|一键采集)$/.test(t));
      }"""
        )
        if btns:
            print(f"poll {i}: buttons:", btns)
            break
        time.sleep(1)
    else:
        print("no submit button appeared; dumping all btn-like:")
        print(
            pg.evaluate(
                """() => {
          const vis = e => e.offsetParent !== null;
          return Array.from(document.querySelectorAll('button')).filter(vis)
            .map(e => ({t: (e.innerText||'').trim(), cls: String(e.className).slice(0,30)})).slice(0,15);
        }"""
            )
        )
