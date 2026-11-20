"""真实认领（严谨版）：未认领筛选 → 选 1 条 → 精确选全托管店铺 → 校验后确定。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
COLLECT_URL = "https://erp.dianxiaobao.net/goods/common/copy"
TARGET = "Shop1105202845"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(5000)

    # 未认领 tab
    try:
        pg.get_by_text("未认领", exact=True).first.click(timeout=4000)
        pg.wait_for_timeout(2000)
    except Exception as e:
        print("tab:", type(e).__name__)

    rows = pg.evaluate("""
    () => Array.from(document.querySelectorAll('tbody tr'))
      .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 70)).slice(0, 8)
    """)
    print("rows:", json.dumps(rows, ensure_ascii=False))

    # 勾第 1 行
    pg.evaluate("""
    () => {
      const boxes = Array.from(document.querySelectorAll('tbody input[type=checkbox]'));
      boxes.forEach((b, i) => { if (b.checked !== (i === 0)) b.click(); });
    }
    """)
    pg.wait_for_timeout(500)

    # 批量认领
    pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button, span, a'))
        .find(e => (e.innerText || '').trim() === '批量认领');
      if (btn) btn.click();
    }
    """)
    pg.wait_for_timeout(3000)

    # 精确点目标店铺的复选框/行
    sel = pg.evaluate(f"""
    () => {{
      const mods = Array.from(document.querySelectorAll('.ivu-modal'))
        .filter(e => e.offsetParent);
      const m = mods[mods.length - 1];
      if (!m) return 'no-modal';
      // 找包含目标店铺名的最小元素，向上找含 input 的容器
      const els = Array.from(m.querySelectorAll('*')).filter(e =>
        (e.innerText || '').includes('{TARGET}'));
      const small = els.sort((a, b) => a.innerText.length - b.innerText.length)[0];
      if (!small) return 'target-not-found';
      let holder = small;
      for (let k = 0; k < 5 && holder; k++) {{
        const inp = holder.querySelector('input[type=checkbox], input[type=radio]');
        if (inp) {{ inp.click(); return 'input-clicked'; }}
        holder = holder.parentElement;
      }}
      small.click();
      return 'row-clicked';
    }}
    """)
    print("select:", sel)
    pg.wait_for_timeout(1200)

    # 校验选中状态
    state = pg.evaluate(f"""
    () => {{
      const mods = Array.from(document.querySelectorAll('.ivu-modal')).filter(e => e.offsetParent);
      const m = mods[mods.length - 1];
      if (!m) return {{modal: false}};
      const items = Array.from(m.querySelectorAll('label, li, [class*="item"]'))
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length < 60 && /Shop|cn11/.test(t));
      const inputs = Array.from(m.querySelectorAll('input')).map(e => e.checked);
      return {{modal: true, items, inputs, bodyHasPlease: m.innerText.includes('请选择店铺')}};
    }}
    """)
    print("state:", json.dumps(state, ensure_ascii=False)[:500])
    pg.screenshot(path=str(DATA / "claim_v2_selected.png"))

    ok = state.get("modal") and any(
        (t or "").find(TARGET) >= 0 for t in state.get("items", []))
    if ok:
        pg.evaluate("""
        () => {
          const mods = Array.from(document.querySelectorAll('.ivu-modal')).filter(e => e.offsetParent);
          const m = mods[mods.length - 1];
          const btn = m && Array.from(m.querySelectorAll('button'))
            .find(e => (e.innerText || '').trim() === '确定');
          if (btn) btn.click();
        }
        """)
        print("clicked 确定")
        pg.wait_for_timeout(6000)
        after = pg.evaluate("""
        () => ({
          tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-300)
        })
        """)
        print(json.dumps(after, ensure_ascii=False)[:600])
    else:
        print("selection not confirmed; NOT clicking 确定")
