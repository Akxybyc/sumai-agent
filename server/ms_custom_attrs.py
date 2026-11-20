"""妙手「自定义属性」英文化。

结构：成对 input，placeholder 分别为「属性名」「属性值」。
策略：读中文键值 → 词典优先，未命中交 LLM 批量翻译 → 写回（可 dry_run）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent.attrs_en import KEY_MAP, has_cjk, translate  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "data"


def _page(browser):
    pages = [x for c in browser.contexts for x in c.pages if "aliexpress_fc" in x.url]
    return pages[0] if pages else None


def read_pairs(pg) -> list[dict]:
    return pg.evaluate(
        """() => {
      const names = Array.from(document.querySelectorAll('input[placeholder="属性名"]'));
      const vals = Array.from(document.querySelectorAll('input[placeholder="属性值"]'));
      const out = [];
      names.forEach((n, i) => {
        const v = vals[i];
        if (!v) return;
        out.push({name: (n.value || '').trim(), value: (v.value || '').trim()});
      });
      return out;
    }"""
    )


def _llm_translate(cfg: dict, pairs: list[dict]) -> dict:
    """优先用妙手「产品翻译」（免费、专业术语准），失败再退回大模型。"""
    todo = set()
    for p in pairs:
        for k in (p["name"], p["value"]):
            if k and has_cjk(k):
                todo.add(k)
    if not todo:
        return {}

    # 首选：妙手文本翻译（不走图片额度）
    try:
        import ms_api
        r = ms_api.translate_strings(sorted(todo))
        if r.get("ok") and r.get("map"):
            return r["map"]
    except Exception:
        pass

    from agent import llm_agent

    prompt = (
        "把下面这些跨境电商商品属性（中文）翻译成英文，用于速卖通商品属性。\n"
        "要求：属性名用标准英文属性名（如 材质→Material、货号→Item No.）；"
        "属性值用简短英文（如 塑料→Plastic、现代简约→Modern Minimalist、否→No）。\n"
        "只输出 JSON 对象，键是原中文，值是英文，不要解释。\n\n"
        + json.dumps(sorted(todo), ensure_ascii=False)
    )
    try:
        resp = llm_agent._post(cfg, {"model": cfg.get("model") or "deepseek-chat",
                                     "messages": [{"role": "user", "content": prompt}],
                                     "temperature": 0})
        text = resp["choices"][0]["message"]["content"].strip()
        s, e = text.find("{"), text.rfind("}")
        return json.loads(text[s:e + 1]) if s >= 0 else {}
    except Exception:
        return {}


def convert(pg, llm_cfg: dict, dry_run: bool = True) -> dict:
    pairs = read_pairs(pg)
    if not pairs:
        return {"ok": False, "message": "没找到自定义属性（请确认在编辑页）"}

    # 先用词典
    mapped = {}
    for p in pairs:
        for k in (p["name"], p["value"]):
            if k and has_cjk(k):
                base = translate({k: k})  # 尝试走词典
                if base:
                    mapped[k] = list(base.keys())[0]
    # 词典里没有的，交 LLM
    need = {}
    for p in pairs:
        for k in (p["name"], p["value"]):
            if k and has_cjk(k) and k not in mapped:
                need[k] = True
    if need:
        mapped.update(_llm_translate(llm_cfg, [{"name": k, "value": ""} for k in need]))

    plan = []
    for p in pairs:
        en_name = mapped.get(p["name"], KEY_MAP.get(p["name"], "")) or p["name"]
        en_val = mapped.get(p["value"], "") or p["value"]
        plan.append({"cn": f"{p['name']}={p['value']}", "en": f"{en_name}={en_val}",
                     "should_change": has_cjk(p["name"]) or has_cjk(p["value"])})

    if dry_run:
        return {"ok": True, "dry_run": True, "count": len(plan), "plan": plan}

    # 写回
    names = pg.locator('input[placeholder="属性名"]')
    vals = pg.locator('input[placeholder="属性值"]')
    changed = 0
    for i, item in enumerate(plan):
        if not item["should_change"]:
            continue
        en_name, _, en_val = item["en"].partition("=")
        try:
            names.nth(i).fill(en_name.strip())
            pg.wait_for_timeout(80)
            vals.nth(i).fill(en_val.strip())
            pg.wait_for_timeout(120)
            changed += 1
        except Exception:
            continue
    pg.screenshot(path=str(DATA / "ms_custom_attrs_en.png"))
    return {"ok": changed > 0, "changed": changed, "count": len(plan), "plan": plan,
            "message": f"已改写 {changed}/{len(plan)} 行"}
