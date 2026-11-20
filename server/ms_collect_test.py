import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
drafts = json.loads((DATA / "drafts.json").read_text(encoding="utf-8"))
d = drafts[0]
payload = f"{d['source_url']}$${d['title_en'][:110]}"
print("payload:", payload[:120])

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    ta = pg.locator("textarea.jx-textarea__inner").first
    ta.click(timeout=5000)
    ta.fill(payload)
    pg.wait_for_timeout(500)
    # 找采集按钮
    btns = pg.evaluate("""
    () => Array.from(document.querySelectorAll('button'))
      .filter(e => e.offsetParent)
      .map(e => (e.innerText || '').trim())
      .filter(Boolean).slice(0, 15)
    """)
    print("buttons:", btns)
    r = pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button'))
        .filter(e => e.offsetParent)
        .find(e => /开始采集|立即采集|^采集$/.test((e.innerText || '').trim()));
      if (btn) { btn.click(); return (btn.innerText || '').trim(); }
      return null;
    }
    """)
    print("clicked:", r)
    pg.wait_for_timeout(20000)
    state = pg.evaluate("""
    () => ({
      url: location.href,
      toast: (document.querySelector('.jx-message, [class*="message"]') || {}).innerText || '',
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-350)
    })
    """)
    print(json.dumps(state, ensure_ascii=False, indent=2)[:900])
    pg.screenshot(path=str(DATA / "ms_collect_test.png"))
