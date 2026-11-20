import json

import ms_batch

cfg = json.load(open("D:/WorkBuddy/sumai_agent/data/settings.json", encoding="utf-8"))["llm"]
import sys
lim = int(sys.argv[1]) if len(sys.argv) > 1 else 2
r = ms_batch.batch_scan(limit=lim, llm_cfg=cfg)
print(r["message"])
for i, x in enumerate(r["results"], 1):
    print(f"{i}. {x['title'][:24]} | 翻译 {x.get('attrs')} / {x.get('sku')} | 可保存={x.get('saved')}")
    miss = x.get("missing") or []
    if miss:
        for mm in miss[:6]:
            print("     缺:", mm)
    elif x.get("reason"):
        print("     异常:", x["reason"])
json.dump(r, open("D:/WorkBuddy/sumai_agent/data/batch_scan.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
