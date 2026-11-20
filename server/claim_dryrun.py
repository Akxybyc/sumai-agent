"""批量认领演练：勾选 2 条 → 批量认领 → 导出弹窗内容 → 取消（不提交）。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
COLLECT_URL = "https://erp.dianxiaobao.net/goods/common/copy"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "dianxiaobao" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.goto(COLLECT_URL, wait_until="domcontentloaded", timeout=60000)
    if COLLECT_URL not in pg.url:
        pg.goto(COLLECT_URL, wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(4000)

    # 1) 勾选前两行
    r = pg.evaluate("""
    () => {
      const boxes = Array.from(document.querySelectorAll('tbody input[type=checkbox]')).slice(0, 2);
      boxes.forEach(b => { if (!b.checked) b.click(); });
      return boxes.length;
    }
    """)
    print("checked rows:", r)
    pg.wait_for_timeout(600)

    # 2) 点批量认领
    r2 = pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button, span, a'))
        .find(e => (e.innerText || '').trim() === '批量认领');
      if (btn) { btn.click(); return true; }
      return false;
    }
    """)
    print("clicked 批量认领:", r2)
    pg.wait_for_timeout(3000)

    # 3) 导出弹窗内容
    data = pg.evaluate("""
    () => {
      const t = (document.body.innerText || '').replace(/\\s+/g, ' ');
      const vis = (e) => e.offsetParent !== null;
      const mods = Array.from(document.querySelectorAll('[class*="modal"],[class*="dialog"],[class*="Modal"],[class*="Dialog"]'))
        .filter(vis);
      const dlg = mods.map(m => ({
        cls: String(m.className).slice(0, 60),
        text: (m.innerText || '').replace(/\\s+/g, ' ').slice(0, 500),
        inputs: Array.from(m.querySelectorAll('input,select')).filter(vis)
          .map(e => ({tag: e.tagName.toLowerCase(), ph: e.placeholder || '', val: (e.value||'').slice(0,30)})),
        buttons: Array.from(m.querySelectorAll('button')).filter(vis)
          .map(e => (e.innerText || '').trim()).filter(Boolean)
      }));
      return {
        hasModal: mods.length > 0,
        dialogs: dlg,
        tail: t.slice(-400)
      };
    }
    """)
    (DATA / "claim_dialog.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1500])

    # 4) 截图留证，然后取消
    pg.screenshot(path=str(DATA / "claim_dryrun.png"))
    pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button'))
        .find(e => (e.innerText || '').trim() === '取消');
      if (btn) btn.click();
    }
    """)
    print("cancelled.")
