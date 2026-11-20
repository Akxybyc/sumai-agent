import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
drafts = json.loads((DATA / "drafts.json").read_text(encoding="utf-8"))
d = drafts[0]
payload = f"{d['source_url']}$${d['title_en'][:110]}"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "common_collect_box" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.goto("https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy",
                wait_until="domcontentloaded", timeout=60000)
    pg.reload(wait_until="domcontentloaded")
    pg.bring_to_front()
    pg.wait_for_timeout(5000)
    # 关掉可能的提示
    pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button, a, div, span'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '我知道了')[0];
      if (btn) btn.click();
    }
    """)
    pg.wait_for_timeout(800)
    ta = pg.locator("textarea.jx-textarea__inner").first
    ta.click(timeout=5000)
    ta.fill(payload)
    pg.wait_for_timeout(500)
    btns = pg.evaluate("""
    () => Array.from(document.querySelectorAll('button'))
      .filter(e => e.offsetParent)
      .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 18)
    """)
    print("buttons:", btns)
    clicked = pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button'))
        .filter(e => e.offsetParent)
        .find(e => /^(开始采集|立即采集|采集)$/.test((e.innerText || '').trim()));
      if (btn) { btn.click(); return (btn.innerText || '').trim(); }
      return null;
    }
    """)
    print("clicked:", clicked)
    if clicked:
        pg.wait_for_timeout(25000)
    state = pg.evaluate("""
    () => ({
      toast: Array.from(document.querySelectorAll('[class*="message"], [class*="toast"]'))
        .filter(e => e.offsetParent).map(e => (e.innerText||'').trim()).slice(0, 3),
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-300)
    })
    """)
    print(json.dumps(state, ensure_ascii=False, indent=2)[:800])
    pg.screenshot(path=str(DATA / "ms_collect_after.png"))
