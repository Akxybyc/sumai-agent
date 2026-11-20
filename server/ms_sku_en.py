"""妙手 SKU/销售属性英文化。

结构：
- 销售属性名（颜色/尺寸/容量）为文本
- 每个属性值旁有 input[placeholder="自定义名称"]，改它即可改 SKU 名称
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent.attrs_en import has_cjk  # noqa: E402
from ms_custom_attrs import _llm_translate  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"

import re as _re

_ALLOWED = _re.compile(r"[^A-Za-z0-9 .\-()/]")


def sanitize(text: str) -> str:
    """妙手限制：自定义名称只可输入英文、数字和 . - ( ) —— 其余字符一律清掉。"""
    t = (text or "").replace("°", " Deg ").replace("*", " ").replace("+", " ")
    t = _ALLOWED.sub(" ", t)
    t = _re.sub(r"\s{2,}", " ", t).strip(" -")
    return t[:120]


ATTR_KEY = {"颜色": "Color", "尺寸": "Size", "容量": "Capacity", "规格": "Specification",
            "款式": "Style", "型号": "Model", "口味": "Flavor", "重量": "Weight"}


def read_values(pg) -> list[dict]:
    """读销售属性里的自定义名称值。"""
    return pg.evaluate(
        """() => {
      const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      return Array.from(document.querySelectorAll('input[placeholder="自定义名称"]'))
        .filter(vis)
        .map((i, idx) => ({idx, value: (i.value || '').trim()}))
        .filter(o => o.value);
    }"""
    )


def convert(pg, llm_cfg: dict, dry_run: bool = True) -> dict:
    vals = read_values(pg)
    if not vals:
        return {"ok": False, "message": "没找到 SKU 自定义名称（请确认在编辑页销售属性区）"}

    todo = [v["value"] for v in vals if has_cjk(v["value"])]
    if not todo:
        return {"ok": True, "count": 0, "message": "SKU 名称已无中文"}

    mapping = {}
    for cn, en in ATTR_KEY.items():
        mapping[cn] = en
    mapping.update(_llm_translate(llm_cfg, [{"name": t, "value": ""} for t in todo]))

    plan = []
    for v in vals:
        cn = v["value"]
        en = mapping.get(cn, "")
        en2 = sanitize(en) if en else ""
        plan.append({"cn": cn, "en": en2 or cn, "change": bool(en2) and en2 != cn})
        if en2:
            mapping[cn] = en2

    if dry_run:
        return {"ok": True, "dry_run": True, "count": len(plan), "plan": plan}

    # 只在「可见」的输入框上写，避免 nth() 命中隐藏元素导致静默失败
    handles = pg.query_selector_all('input[placeholder="自定义名称"]')
    visible = []
    for h in handles:
        box = h.bounding_box()
        if box and box["width"] > 20:
            visible.append(h)

    changed = 0
    failed = []
    for idx, h in enumerate(visible):
        try:
            cur = h.input_value()
        except Exception:
            continue
        en = mapping.get(cur)
        if not en or en == cur:
            continue
        try:
            h.fill(en)
            pg.wait_for_timeout(150)
            changed += 1
        except Exception as e:  # noqa: BLE001
            failed.append(f"{cur[:12]}:{type(e).__name__}")
    pg.wait_for_timeout(500)
    pg.screenshot(path=str(DATA / "ms_sku_en.png"))
    return {"ok": changed > 0, "changed": changed, "count": len(plan), "plan": plan,
            "failed": failed[:5],
            "message": f"SKU 名称改写 {changed}/{len(plan)} 个"
                       + (f"（失败 {len(failed)}）" if failed else "")}
