"""给已有草稿补缩略图（从 1688 详情页抓主图）。"""
import json
from pathlib import Path

import rpa1688

DATA = Path("D:/WorkBuddy/sumai_agent/data")
drafts_file = DATA / "drafts.json"
drafts = json.loads(drafts_file.read_text(encoding="utf-8"))

seen = {}
for d in drafts:
    if d.get("images"):
        seen[d["source_url"]] = d["images"]
        continue
    url = d.get("source_url") or ""
    if not url:
        continue
    if url in seen:
        d["images"] = seen[url]
        continue
    det = rpa1688.collect_detail(url, 9222)
    imgs = (det.get("images") or [])[:8] if det.get("ok") else []
    d["images"] = imgs
    seen[url] = imgs
    print(url[-20:], "->", len(imgs), "imgs", flush=True)

drafts_file.write_text(json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8")
print("done, drafts with images:", sum(1 for d in drafts if d.get("images")))
