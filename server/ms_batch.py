"""妙手批量翻译：逐条打开全托管采集箱商品 → 自定义属性 + SKU 转英文 → 保存 → 下一条。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

import ms_custom_attrs
import ms_sku_en

DATA = Path(__file__).resolve().parent.parent / "data"


def _page(browser):
    cands = [x for c in browser.contexts for x in c.pages
             if "aliexpress_fc" in x.url and "collect_box" in x.url and "agent" not in x.url]
    return cands[0] if cands else None


def _rows_info(pg) -> list[dict]:
    return pg.evaluate(
        """() => [...document.querySelectorAll('.jx-pro-virtual-table__row')].map((r, i) => {
      const txt = (r.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
      const hasEdit = [...r.querySelectorAll('a,span,button,div')]
        .some(e => (e.innerText || '').trim() === '编辑');
      return {idx: i, title: txt[0] || '', hasEdit};
    })"""
    )


def _click_edit(pg, idx: int) -> bool:
    return bool(pg.evaluate(
        """(i) => {
      const rows = [...document.querySelectorAll('.jx-pro-virtual-table__row')];
      const r = rows[i];
      if (!r) return false;
      const btn = [...r.querySelectorAll('a,span,button,div')]
        .find(e => (e.innerText || '').trim() === '编辑');
      if (btn) { btn.click(); return true; }
      return false;
    }""",
        idx,
    ))


def _dismiss_dialogs(pg) -> int:
    """关掉 el-message-box 提示（保存失败/校验提示），返回关闭数量。"""
    n = 0
    for _ in range(3):
        ok = pg.evaluate(
            """() => {
          const w = [...document.querySelectorAll('.el-message-box__wrapper')].filter(e => e.offsetParent);
          if (!w.length) return null;
          const box = w[w.length - 1];
          const txt = (box.innerText || '').replace(/\\s+/g, ' ').slice(0, 120);
          const btn = [...box.querySelectorAll('button')].find(e => /确定|知道了|关闭|取消/.test(e.innerText));
          if (btn) { btn.click(); return txt; }
          return '';
        }"""
        )
        if ok is None:
            break
        n += 1
        pg.wait_for_timeout(700)
    return n


def _errors(pg) -> list[str]:
    return pg.evaluate(
        """() => [...document.querySelectorAll('.el-form-item__error')]
          .filter(e => e.offsetParent).map(e => (e.innerText || '').trim())
          .filter(Boolean).slice(0, 8)"""
    )


def _save(pg) -> bool:
    """点保存（编辑抽屉底部）。"""
    ok = pg.evaluate(
        """() => {
      const btns = [...document.querySelectorAll('button')].filter(e => e.offsetParent);
      const t = btns.find(e => ['保存修改', '保存', '保存并关闭', '确定保存', '确定'].includes((e.innerText || '').trim()));
      if (t) { t.click(); return true; }
      return false;
    }"""
    )
    return ok


def _close_drawer(pg) -> None:
    pg.evaluate(
        """() => {
      const btns = [...document.querySelectorAll('button')].filter(e => e.offsetParent);
      const t = btns.find(e => ['取消', '关闭', '返回'].includes((e.innerText || '').trim()));
      if (t) t.click();
    }"""
    )
    pg.wait_for_timeout(1200)


def batch(limit: int = 5, port: int = 9222, llm_cfg: dict | None = None,
          dry_run: bool = False) -> dict:
    llm_cfg = llm_cfg or {}
    results = []
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            return {"ok": False, "message": "请先在妙手打开「速卖通全托管 → 采集箱」列表"}
        pg.bring_to_front()
        pg.wait_for_timeout(1500)

        rows = [r for r in _rows_info(pg) if r["hasEdit"]]
        done_titles: set[str] = set()
        todo = rows[:limit]

        for n, r in enumerate(todo, start=1):
            title = r["title"][:24]
            try:
                if not _click_edit(pg, r["idx"]):
                    results.append({"title": title, "ok": False, "reason": "点不到编辑"})
                    continue
                pg.wait_for_timeout(6500)

                a = ms_custom_attrs.convert(pg, llm_cfg, dry_run)
                s = ms_sku_en.convert(pg, llm_cfg, dry_run)
                _dismiss_dialogs(pg)
                saved = False if dry_run else _save(pg)
                pg.wait_for_timeout(1800)
                dlg = _dismiss_dialogs(pg) if not dry_run else 0
                errs = _errors(pg) if not dry_run else []
                if not dry_run and saved and not errs:
                    _close_drawer(pg)

                results.append({
                    "title": title,
                    "ok": bool(a.get("ok") or s.get("ok")),
                    "attrs": a.get("message") or a.get("count"),
                    "sku": s.get("message") or s.get("count"),
                    "saved": saved,
                    "blocked_by": errs,
                })
                done_titles.add(title)
            except Exception as e:  # noqa: BLE001
                results.append({"title": title, "ok": False, "reason": f"{type(e).__name__}: {e}"})
                try:
                    _close_drawer(pg)
                except Exception:
                    pass

    ok_n = sum(1 for x in results if x.get("ok"))
    return {"ok": ok_n > 0, "done": ok_n, "total": len(todo), "results": results,
            "message": f"完成 {ok_n}/{len(todo)} 条"}


if __name__ == "__main__":
    print(json.dumps(batch(limit=1, dry_run=True), ensure_ascii=False, indent=1)[:800])


def _cancel(pg) -> bool:
    """放弃本次修改：点抽屉里的「取消」，没有就点右上角关闭。"""
    ok = pg.evaluate(
        """() => {
      const btns = [...document.querySelectorAll('button')].filter(e => e.offsetParent);
      const t = btns.find(e => ['取消', '关闭'].includes((e.innerText || '').trim()));
      if (t) { t.click(); return true; }
      const x = document.querySelector('.el-drawer__close-btn, .el-dialog__headerbtn');
      if (x) { x.click(); return true; }
      return false;
    }"""
    )
    pg.wait_for_timeout(1200)
    # 若弹了"放弃修改？"确认框，点确定
    pg.evaluate(
        """() => {
      const w = [...document.querySelectorAll('.el-message-box__wrapper')].filter(e => e.offsetParent);
      if (!w.length) return;
      const btn = [...w[w.length - 1].querySelectorAll('button')].find(e => /确定|是/.test(e.innerText));
      if (btn) btn.click();
    }"""
    )
    return ok


def batch_scan(limit: int = 10, port: int = 9222, llm_cfg: dict | None = None) -> dict:
    """段1：逐条翻译 → 试保存 → 抓必填项 → 取消 → 下一条。不改动数据。"""
    llm_cfg = llm_cfg or {}
    results: list[dict] = []
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            return {"ok": False, "message": "请先在妙手打开「速卖通全托管 → 采集箱」列表"}
        pg.bring_to_front()
        pg.wait_for_timeout(1200)

        rows = [r for r in _rows_info(pg) if r["hasEdit"]][:limit]
        if not rows:
            return {"ok": False, "message": "列表里没有可编辑的商品"}

        for n, r in enumerate(rows, start=1):
            title = r["title"][:26]
            try:
                _dismiss_dialogs(pg)
                if not _click_edit(pg, r["idx"]):
                    results.append({"title": title, "ok": False, "missing": [], "reason": "点不到编辑"})
                    continue
                pg.wait_for_timeout(6500)

                a = ms_custom_attrs.convert(pg, llm_cfg, False)
                s = ms_sku_en.convert(pg, llm_cfg, False)
                _dismiss_dialogs(pg)

                _save(pg)
                pg.wait_for_timeout(2000)
                _dismiss_dialogs(pg)          # 关掉"保存失败"弹窗
                missing = _errors(pg)          # 抓必填项
                saved_ok = not missing

                if not saved_ok:
                    _cancel(pg)                # 放弃修改
                _close_drawer(pg)

                results.append({
                    "title": title,
                    "ok": True,
                    "attrs": a.get("message") or f"{a.get('count')} 行",
                    "sku": s.get("message") or f"{s.get('count')} 个",
                    "saved": saved_ok,
                    "missing": missing,
                })
            except Exception as e:  # noqa: BLE001
                try:
                    _cancel(pg)
                    _close_drawer(pg)
                except Exception:
                    pass
                results.append({"title": title, "ok": False, "missing": [],
                                "reason": f"{type(e).__name__}: {e}"})

    ready = sum(1 for x in results if x.get("saved"))
    need = sum(1 for x in results if x.get("missing"))
    return {
        "ok": True, "scanned": len(results), "ready": ready, "need_fix": need,
        "results": results,
        "message": f"扫描 {len(results)} 条：可直接保存 {ready} 条，待补填 {need} 条",
    }
