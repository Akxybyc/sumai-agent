"""按需补图：给前 6 个缺图草稿抓 1688 主图。"""
import json
from pathlib import Path

import rpa1688

f = Path("D:/WorkBuddy/sumai_agent/data/drafts.json")
drafts = json.loads(f.read_text(encoding="utf-8"))
done_urls = {d["source_url"]: d["images"] for d in drafts if d.get("images") and d.get("source_url")}

count = 0
for d in drafts:
    if count >= 30:
        break
    if d.get("images"):
        continue
    url = d.get("source_url")
    if not url:
        continue
    if url in done_urls:
        d["images"] = done_urls[url]
        continue
    r = rpa1688.collect_detail(url, 9222)
    imgs = (r.get("images") or [])[:8] if r.get("ok") else []
    d["images"] = imgs
    done_urls[url] = imgs
    count += 1
    print(f"{count}. {url[-18:]} -> {len(imgs)} imgs", flush=True)
    f.write_text(json.dumps(drafts, ensure_ascii=False, indent=1), encoding="utf-8")

print("with images:", sum(1 for d in drafts if d.get("images")), "/", len(drafts))
