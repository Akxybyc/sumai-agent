"""按新核心词识别重建现有草稿的英文标题（不动其它字段）。"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from content import build_title_v2, core_from_item, pick_pack  # noqa: E402

F = Path("D:/WorkBuddy/sumai_agent/data/drafts.json")
drafts = json.loads(F.read_text(encoding="utf-8"))

changed = 0
for d in drafts:
    cat_cn = d.get("category_cn") or "家居"
    core = core_from_item(d.get("title_cn", ""), cat_cn)
    pack = pick_pack(cat_cn)
    title, check = build_title_v2(core, pack["attr"], pack["longtail"], pack["flow"],
                                  seed=d.get("source_id") or d.get("title_cn", ""))
    old = d.get("title_en", "")
    d["title_en"] = title[:180]
    if isinstance(d.get("content"), dict):
        d["content"]["title"] = {"en": d["title_en"], "zh": d.get("title_cn", "")}
        d["content"]["title_check"] = check
    if old != d["title_en"]:
        changed += 1
    print(f"{d.get('title_cn','')[:16]:18} core={core:22} {check['letters']}字母 ok={check['ok']}")
    print(f"   旧: {old[:70]}")
    print(f"   新: {d['title_en'][:70]}")

F.write_text(json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"\n共更新 {changed} 条")
