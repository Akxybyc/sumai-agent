"""公共采集箱 → 认领到「速卖通全托管」（UI 自动化）。

API 不支持 aliexpress 平台，只能走界面：搜索 → 切「未认领」→ 全选 → 认领到 → 选速卖通全托管。
"""

from __future__ import annotations

import time

from playwright.sync_api import sync_playwright

LIST_URL = "https://erp.91miaoshou.com/common_collect_box/items"
TARGET = "速卖通全托管"


def _page(b):
    for c in b.contexts:
        for pg in c.pages:
            if "common_collect_box/items" in pg.url:
                return pg
    pg = b.contexts[0].new_page()
    return pg


def _counts(pg) -> dict:
    t = pg.evaluate("() => document.body.innerText") or ""
    out = {}
    for line in t.splitlines():
        s = line.strip()
        for k in ("全部", "未认领", "已认领"):
            if s.startswith(k + " (") and s.endswith(")"):
                try:
                    out[k] = int(s.split("(")[1].rstrip(")"))
                except Exception:
                    pass
    return out


def claim(port: int = 9222, dry_run: bool = False, wait: int = 8) -> dict:
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        pg.bring_to_front()
        if "common_collect_box/items" not in pg.url:
            pg.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)

        # 触发列表加载
        pg.evaluate("""() => {
          const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent)
                      .find(e => (e.innerText || '').trim() === '搜索');
          if (b) b.click();
        }""")
        pg.wait_for_timeout(4000)

        before = _counts(pg)
        if before.get("未认领", 0) == 0:
            return {"ok": False, "nothing": True, "counts": before,
                    "message": f"没有待认领商品（全部 {before.get('全部', 0)}，未认领 0，已认领 {before.get('已认领', 0)}）"}

        # 切到「未认领」
        pg.evaluate("""() => {
          const els = [...document.querySelectorAll('*')].filter(e => e.offsetParent && /^未认领\\s*\\(/.test((e.innerText || '').trim()));
          if (els.length) els[els.length - 1].click();
        }""")
        pg.wait_for_timeout(2500)

        # 全选
        pg.evaluate("""() => {
          const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent)
                      .find(e => (e.innerText || '').trim() === '全选');
          if (b) b.click();
        }""")
        pg.wait_for_timeout(1200)

        if dry_run:
            return {"ok": True, "dry_run": True, "counts": before,
                    "message": f"预演：待认领 {before.get('未认领', 0)} 条，已勾选（未点认领）"}

        # 点「认领到」
        clicked = pg.evaluate("""() => {
          const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent)
                      .find(e => /^认领到/.test((e.innerText || '').trim()));
          if (b) { b.click(); return true; }
          return false;
        }""")
        if not clicked:
            return {"ok": False, "message": "找不到「认领到」按钮"}
        pg.wait_for_timeout(1800)

        # 菜单里选「AliExpress速卖通全托管」
        picked = pg.evaluate("""(target) => {
          const cands = [...document.querySelectorAll('li,div,span,a')]
            .filter(e => e.offsetParent && (e.innerText || '').trim().includes(target));
          if (!cands.length) return false;
          cands.sort((a, b) => (a.innerText || '').length - (b.innerText || '').length);
          cands[0].click();
          return true;
        }""", TARGET)
        if not picked:
            return {"ok": False, "message": f"认领菜单里没找到「{TARGET}」"}

        pg.wait_for_timeout(wait * 1000)
        after = _counts(pg)
        moved = before.get("未认领", 0) - after.get("未认领", 0)
        return {"ok": moved > 0, "before": before, "after": after, "claimed": moved,
                "message": (f"已认领 {moved} 条到{TARGET}" if moved > 0
                            else "点了认领但数量没变化，可能需要选店铺或手工确认")}


if __name__ == "__main__":
    print(claim(dry_run=True))
