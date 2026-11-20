"""妙手类目属性自动填充（真实鼠标事件版）。

已验证：Element UI 下拉必须用真实鼠标点击（JS click 无效）。
规则（用户指定）：
- 产地 → 中国大陆(Origin)
- 高关注化学品 → 无
- 物流属性 → 含电路板/电池/电机/磁铁/无线/充电 → 弱电和弱磁；否则 普货
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path(__file__).resolve().parent.parent / "data"
TEMPLATES = DATA / "ms_attr_templates.json"

FIXED = {
    "产地": "中国大陆",
    "高关注化学品": "无",
}

# 弱电弱磁判定关键词
WEAK_KW = ["电路板", "pcba", "pcb", "电池", "锂电", "充电", "马达", "电机", "磁铁",
           "磁性", "无线", "蓝牙", "led", "灯珠", "芯片", "电子"]
LIQUID_KW = ["液体", "喷雾", "精油", "香水", "胶水", "膏", "液体粉"]

FIELDS = ["产地", "材质", "高关注化学品", "功能", "特性", "风格", "固定方式", "外形因素"]


def _page(browser):
    pages = [x for c in browser.contexts for x in c.pages if "aliexpress_fc" in x.url]
    return pages[0] if pages else None


def _ensure_editor(pg) -> bool:
    if pg.evaluate("() => !!document.querySelector('.category-attribute-list')"):
        return True
    pg.evaluate(
        """() => {
      const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
      for (const r of rows) {
        const btn = Array.from(r.querySelectorAll('a, span, button, div'))
          .find(e => (e.innerText || '').trim() === '编辑');
        if (btn) { btn.click(); return true; }
      }
    }"""
    )
    pg.wait_for_timeout(7000)
    return pg.evaluate("() => !!document.querySelector('.category-attribute-list')")


def _field_box(pg, field: str):
    return pg.evaluate(
        """(name) => {
      const it = Array.from(document.querySelectorAll('.category-attribute-item'))
        .find(e => (e.innerText || '').trim().startsWith(name));
      if (!it) return null;
      const el = it.querySelector('.el-select') || it.querySelector('.el-input__inner');
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {x: r.x + r.width / 2, y: r.y + r.height / 2};
    }""",
        field,
    )


def _scroll_field(pg, field: str) -> None:
    pg.evaluate(
        """(name) => {
      const it = Array.from(document.querySelectorAll('.category-attribute-item'))
        .find(e => (e.innerText || '').trim().startsWith(name));
      const el = it && (it.querySelector('.el-select') || it.querySelector('.el-input__inner'));
      if (el) el.scrollIntoView({block: 'center'});
    }""",
        field,
    )
    pg.wait_for_timeout(500)


def _human_click(pg, x: float, y: float) -> None:
    """模拟真人点击：移动 → 停顿 → 按下 → 松开。"""
    pg.mouse.move(x, y, steps=8)
    pg.wait_for_timeout(180)
    pg.mouse.down()
    pg.wait_for_timeout(90)
    pg.mouse.up()
    pg.wait_for_timeout(150)


def _visible_options(pg):
    """取当前真正可见、且有内容的那个下拉弹层（按尺寸判断可见性）。"""
    return pg.evaluate(
        """() => {
      const dds = Array.from(document.querySelectorAll('.el-select-dropdown'))
        .filter(e => { const r = e.getBoundingClientRect(); return r.height > 20 && r.width > 50; });
      let best = null, bestN = 0;
      for (const dd of dds) {
        const items = Array.from(dd.querySelectorAll('.el-select-dropdown__item'));
        if (items.length > bestN) { best = items; bestN = items.length; }
      }
      if (!best) return [];
      const out = [];
      for (const e of best) {
        const r = e.getBoundingClientRect();
        if (r.width > 5 && r.height > 5) {
          out.push({text: (e.innerText || '').replace(/\\s+/g, ' ').trim(),
                    x: r.x + r.width / 2, y: r.y + r.height / 2});
        }
      }
      return out.filter(o => o.text);
    }"""
    )


def _current_value(pg, field: str) -> str:
    return pg.evaluate(
        """(name) => {
      const it = Array.from(document.querySelectorAll('.category-attribute-item'))
        .find(e => (e.innerText || '').trim().startsWith(name));
      if (!it) return '';
      const t = it.querySelector('.el-tag, .el-select__tags-text');
      const i = it.querySelector('.el-input__inner');
      return ((t && t.innerText.trim()) || (i && i.value) || '').trim();
    }""",
        field,
    )


def _match(options: list[dict], want: str):
    w = want.strip()
    # 1) 完全匹配正文部分（括号前）
    for o in options:
        head = o["text"].split("(")[0].strip()
        if head == w:
            return o
    # 2) 选项以目标开头
    for o in options:
        if o["text"].startswith(w):
            return o
    # 3) 包含
    for o in options:
        if w in o["text"]:
            return o
    return None


def set_field(pg, field: str, want: str) -> dict:
    """用真实鼠标把某个属性设为 want。"""
    opts = []
    box = None
    for attempt in range(3):
        box = _field_box(pg, field)
        if not box:
            time.sleep(0.5)
            continue
        _human_click(pg, box["x"], box["y"])
        time.sleep(1.8)
        opts = _visible_options(pg)
        if opts:
            break
    if not box:
        return {"field": field, "ok": False, "reason": "未找到控件"}
    if not opts:
        return {"field": field, "ok": False, "reason": "下拉未展开"}
    hit = _match(opts, want)
    if not hit:
        return {"field": field, "ok": False, "reason": "无匹配选项", "want": want,
                "sample": [o["text"] for o in opts[:8]]}
    _human_click(pg, hit["x"], hit["y"])
    time.sleep(1.2)
    got = _current_value(pg, field)
    return {"field": field, "ok": bool(got), "want": want, "pick": hit["text"], "value": got}


def infer_logistics(text: str) -> str:
    t = (text or "").lower()
    if any(k in t for k in LIQUID_KW):
        return "液体"
    if any(k in t for k in WEAK_KW):
        return "弱电和弱磁"
    return "普货"


def load_templates() -> dict:
    try:
        if TEMPLATES.exists():
            return json.loads(TEMPLATES.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def save_template(category: str, values: dict) -> dict:
    tpl = load_templates()
    tpl[category] = values
    TEMPLATES.write_text(json.dumps(tpl, ensure_ascii=False, indent=1), encoding="utf-8")
    return tpl[category]


def apply(draft: dict, port: int = 9222, dry_run: bool = False,
          extra: dict | None = None) -> dict:
    """按规则 + 品类模板 + 显式 extra 填充属性。"""
    values = dict(FIXED)
    cat = (draft.get("category_cn") or "").split(">")[-1].strip()
    tpl = load_templates().get(cat) or {}
    values.update({k: v for k, v in tpl.items() if v})
    if extra:
        values.update(extra)

    with sync_playwright() as p:
        b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        pg = _page(b)
        if pg is None:
            return {"ok": False, "message": "未打开妙手页面"}
        if not _ensure_editor(pg):
            return {"ok": False, "message": "没能打开商品编辑页"}

        results = []
        for field, want in values.items():
            if field not in FIELDS:
                continue
            cur = _current_value(pg, field)
            if cur and want.split("(")[0].strip() in cur:
                results.append({"field": field, "ok": True, "skipped": True, "value": cur})
                continue
            if dry_run:
                box = _field_box(pg, field)
                if not box:
                    results.append({"field": field, "ok": False, "reason": "未找到控件"})
                    continue
                pg.mouse.click(box["x"], box["y"])
                time.sleep(1.0)
                opts = _visible_options(pg)
                hit = _match(opts, want)
                results.append({"field": field, "ok": bool(hit),
                                "would_pick": hit["text"] if hit else None,
                                "want": want,
                                "sample": [o["text"] for o in opts[:5]] if not hit else None})
                pg.keyboard.press("Escape")
                time.sleep(0.3)
            else:
                results.append(set_field(pg, field, want))

        if not dry_run:
            pg.screenshot(path=str(DATA / "ms_attrs_applied.png"))
        ok = sum(1 for r in results if r.get("ok"))
        return {"ok": ok == len([r for r in results if not r.get("skipped")]) or ok > 0,
                "applied": ok, "total": len(results), "results": results,
                "message": f"属性处理 {ok}/{len(results)}"}


def set_field_v2(pg, field: str, want: str) -> dict:
    """Playwright 定位器版：自带等待与可点击检查。"""
    try:
        item = pg.locator(".category-attribute-item").filter(has_text=field).first
        item.scroll_into_view_if_needed(timeout=4000)
        sel = item.locator(".el-select").first
        sel.click(timeout=5000)
        pg.wait_for_selector(".el-select-dropdown__item", state="visible", timeout=6000)
    except Exception as e:  # noqa: BLE001
        return {"field": field, "ok": False, "reason": f"打不开下拉：{type(e).__name__}"}

    # 先尝试完全匹配（选项正文）
    try:
        opt = pg.locator(".el-select-dropdown__item:visible").filter(has_text=want).first
        opt.click(timeout=5000)
    except Exception as e:  # noqa: BLE001
        pg.keyboard.press("Escape")
        return {"field": field, "ok": False, "reason": f"选项点不到：{type(e).__name__}"}

    pg.wait_for_timeout(900)
    got = _current_value(pg, field)
    return {"field": field, "ok": bool(got), "want": want, "value": got}
