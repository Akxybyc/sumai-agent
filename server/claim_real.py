"""真实认领第 1 条 → 全托管 Shop1105202845 Store。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
COLLECT_URL = "https://erp.dianxiaobao.net/goods/common/copy"
TARGET = "Shop1105202845"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "dianxiaobao" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
    if COLLECT_URL not in pg.url:
        pg.goto(COLLECT_URL, wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(4000)

    # 只勾第 1 行
    pg.evaluate("""
    () => {
      const boxes = Array.from(document.querySelectorAll('tbody input[type=checkbox]'));
      boxes.forEach((b, i) => { if (b.checked !== (i === 0)) b.click(); });
    }
    """)
    pg.wait_for_timeout(600)

    # 打开批量认领
    pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button, span, a'))
        .find(e => (e.innerText || '').trim() === '批量认领');
      if (btn) btn.click();
    }
    """)
    pg.wait_for_timeout(3000)

    # 在弹窗里选全托管店铺
    sel = pg.evaluate(f"""
    () => {{
      const mods = Array.from(document.querySelectorAll('[class*="modal"],[class*="Modal"]'))
        .filter(e => e.offsetParent);
      const m = mods[0];
      if (!m) return 'no-modal';
      const hit = Array.from(m.querySelectorAll('*')).find(e =>
        (e.innerText || '').includes('{TARGET}') && e.children.length <= 3);
      if (!hit) return 'target-not-found';
      hit.click();
      return 'clicked:' + (hit.innerText || '').replace(/\\s+/g, ' ').slice(0, 40);
    }}
    """)
    print("select store:", sel)
    pg.wait_for_timeout(1000)
    pg.screenshot(path=str(DATA / "claim_real_selected.png"))

    # 确定
    pg.evaluate("""
    () => {
      const mods = Array.from(document.querySelectorAll('[class*="modal"],[class*="Modal"]'))
        .filter(e => e.offsetParent);
      const m = mods[0];
      const btn = m && Array.from(m.querySelectorAll('button')).find(e => (e.innerText || '').trim() === '确定');
      if (btn) btn.click();
    }
    """)
    pg.wait_for_timeout(5000)

    # 验证：已认领 tab
    try:
        pg.get_by_text("已认领", exact=True).first.click(timeout=4000)
        pg.wait_for_timeout(2500)
    except Exception as e:
        print("tab click:", type(e).__name__)

    res = pg.evaluate("""
    () => ({
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-500),
      rows: Array.from(document.querySelectorAll('tbody tr'))
        .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 80)).slice(0, 6)
    })
    """)
    print(json.dumps(res, ensure_ascii=False, indent=2)[:1200])
    pg.screenshot(path=str(DATA / "claim_real_done.png"))
