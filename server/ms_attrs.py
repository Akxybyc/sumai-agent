"""速卖通全托管采集箱 · 类目属性读取与填充（Element UI 下拉）。

字段：产地(Origin) / 材质(Material) / 高关注化学品 / 功能 / 特性 / 风格 / 固定方式 / 外形因素
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path(__file__).resolve().parent.parent / "data"
SCHEMA = DATA / "ae_attr_schema.json"
FIELDS = ["产地", "材质", "高关注化学品", "功能", "特性", "风格", "固定方式", "外形因素"]


def _page(browser):
    pages = [x for c in browser.contexts for x in c.pages if "aliexpress_fc" in x.url]
    return pages[0] if pages else None


def _ensure_editor(pg) -> bool:
    """确保商品编辑抽屉是打开的。"""
    if pg.evaluate("""() => !!document.querySelector('.category-attribute-list')"""):
        return True
    clicked = pg.evaluate(
        """() => {
      const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
      for (const r of rows) {
        const btn = Array.from(r.querySelectorAll('a, span, button, div'))
          .find(e => (e.innerText || '').trim() === '编辑');
        if (btn) { btn.click(); return true; }
      }
      return false;
    }"""
    )
    if clicked:
        pg.wait_for_timeout(6000)
    return bool(pg.evaluate("""() => !!document.querySelector('.category-attribute-list')"""))


def _open_select(pg, field: str) -> bool:
    return bool(pg.evaluate(
        """(name) => {
      const items = Array.from(document.querySelectorAll('.category-attribute-item'));
      const it = items.find(e => (e.innerText || '').trim().startsWith(name));
      if (!it) return false;
      const inp = it.querySelector('.el-select .el-input__inner')
        || it.querySelector('.el-select')
        || it.querySelector('.el-input__inner');
      if (!inp) return false;
      inp.click();
      return true;
    }""",
        field,
    ))


def _read_options(pg) -> list[str]:
    """只读最近打开的那个下拉弹层，避免读到上一个字段的选项。"""
    return pg.evaluate(
        """() => {
      const dds = Array.from(document.querySelectorAll('.el-select-dropdown'))
        .filter(e => e.offsetParent !== null);
      const dd = dds[dds.length - 1];
      if (!dd) return [];
      return Array.from(dd.querySelectorAll('.el-select-dropdown__item'))
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(Boolean);
    }"""
    )


def _close_dropdown(pg) -> None:
    """点页面左上角空白，关掉下拉（不用 Esc，避免关掉整个抽屉）。"""
    try:
        pg.mouse.click(8, 8)
    except Exception:
        pass
    pg.wait_for_timeout(250)


def read_schema(port: int = 9222) -> dict:
    """读取每个属性的可选项与当前已选值。"""
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            return {"ok": False, "message": "未打开妙手商品编辑页"}
        if not _ensure_editor(pg):
            return {"ok": False, "message": "没能打开商品编辑页（请先在采集箱点一条商品的『编辑』）"}
        out = {}
        for f in FIELDS:
            if not _open_select(pg, f):
                out[f] = {"options": [], "selected": [], "error": "未找到控件"}
                continue
            time.sleep(1.3)
            opts = _read_options(pg)
            # 当前已选（el-select 的 tag 文本）
            sel = pg.evaluate(
                """(name) => {
              const items = Array.from(document.querySelectorAll('.category-attribute-item'));
              const it = items.find(e => (e.innerText || '').trim().startsWith(name));
              if (!it) return [];
              return Array.from(it.querySelectorAll('.el-tag, .el-select__tags-text'))
                .map(e => (e.innerText || '').trim()).filter(Boolean);
            }""",
                f,
            )
            out[f] = {"options": opts[:200], "selected": sel}
            _close_dropdown(pg)
        SCHEMA.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
        return {"ok": True, "fields": out, "file": str(SCHEMA)}


def fill(values: dict[str, str], port: int = 9222, dry_run: bool = True) -> dict:
    """按 {字段: 目标选项文本} 填充；dry_run 只匹配不点击。"""
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            return {"ok": False, "message": "未打开妙手商品编辑页"}
        if not _ensure_editor(pg):
            return {"ok": False, "message": "没能打开商品编辑页"}

        results = []
        for field, want in values.items():
            if not want:
                continue
            if not _open_select(pg, field):
                results.append({"field": field, "ok": False, "reason": "未找到控件"})
                continue
            time.sleep(0.9)
            opts = _read_options(pg)
            # 宽松匹配：选项包含目标词，或目标词包含选项主体
            hit = next((o for o in opts if want in o), None) or \
                  next((o for o in opts if o.split("(")[0].strip() in want), None)
            if not hit:
                results.append({"field": field, "ok": False, "want": want,
                                "reason": "无匹配选项", "sample": opts[:8]})
                _close_dropdown(pg)
                continue
            if dry_run:
                results.append({"field": field, "ok": True, "want": want, "pick": hit, "dry_run": True})
                _close_dropdown(pg)
                continue
            clicked = pg.evaluate(
                """(text) => {
              const el = Array.from(document.querySelectorAll('.el-select-dropdown__item'))
                .filter(e => e.offsetParent !== null)
                .find(e => (e.innerText || '').replace(/\\s+/g, ' ').trim() === text);
              if (el) { el.click(); return true; }
              return false;
            }""",
                hit,
            )
            results.append({"field": field, "ok": clicked, "want": want, "pick": hit})
            time.sleep(0.6)

        pg.screenshot(path=str(DATA / "ms_attrs_filled.png"))
        ok = sum(1 for r in results if r.get("ok"))
        return {"ok": ok > 0, "filled": ok, "total": len(values), "results": results,
                "message": f"匹配成功 {ok}/{len(values)}" + ("（dry_run 未点击）" if dry_run else "")}


def audit(port: int = 9222) -> dict:
    """发布前体检：扫描编辑页里必填但为空的项。"""
    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            return {"ok": False, "message": "未打开妙手页面"}
        if not _ensure_editor(pg):
            return {"ok": False, "message": "没能打开商品编辑页"}

        data = pg.evaluate(
            """() => {
          const vis = e => e.offsetParent !== null;
          const out = {category: '', attrs: [], errors: [], sku: [], logistics: ''};

          // 类目
          const catItem = Array.from(document.querySelectorAll('.category-attribute-item, .el-form-item'))
            .find(e => vis(e) && (e.innerText || '').trim().startsWith('类目'));
          if (catItem) {
            const v = catItem.querySelector('.el-input__inner');
            out.category = (v && v.value) || '';
          }

          // 类目属性：已选值 / 请选择
          document.querySelectorAll('.category-attribute-item').forEach((it) => {
            if (!vis(it)) return;
            const name = (it.innerText || '').replace(/\\s+/g, ' ').trim().split(' ')[0];
            const tag = it.querySelector('.el-tag, .el-select__tags-text');
            const inp = it.querySelector('.el-input__inner');
            const val = (tag && tag.innerText.trim()) || (inp && inp.value) || '';
            const empty = !val || /请选择/.test(val);
            out.attrs.push({field: name, value: val, empty});
          });

          // 页面红色错误提示
          document.querySelectorAll('.el-form-item__error').forEach((e) => {
            if (vis(e)) {
              const t = (e.innerText || '').replace(/\\s+/g, ' ').trim();
              if (t) out.errors.push(t);
            }
          });

          // SKU 行：看是否缺 供货价/库存/重量/尺寸
          const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
          if (rows.length) {
            const r = rows[0];
            const inputs = Array.from(r.querySelectorAll('input')).filter(vis);
            out.sku = inputs.map((i) => i.value || '').slice(0, 8);
          }

          // 物流属性
          const lg = Array.from(document.querySelectorAll('.el-form-item, .category-attribute-item'))
            .find(e => vis(e) && (e.innerText || '').startsWith('物流属性'));
          if (lg) {
            const v = lg.querySelector('.el-input__inner');
            out.logistics = (v && v.value) || '';
          }
          return out;
        }"""
        )

        missing = []
        if not data.get("category") or "请选择" in data.get("category", ""):
            missing.append({"field": "类目", "hint": "未选择速卖通类目"})
        for a in data.get("attrs", []):
            if a.get("empty"):
                missing.append({"field": a["field"], "hint": "必填属性未选"})
        for e in data.get("errors", []):
            missing.append({"field": "平台校验", "hint": e})
        if data.get("logistics") in ("", "请选择物流属性"):
            missing.append({"field": "物流属性", "hint": "未选择"})

        pg.screenshot(path=str(DATA / "ms_audit.png"))
        return {"ok": True, "missing": missing, "count": len(missing),
                "detail": data,
                "message": (f"发现 {len(missing)} 项待补" if missing else "必填项看起来都不缺")}
