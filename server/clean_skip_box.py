"""清理公共采集箱里 status=skip（产品已经采集过）的重复记录。"""
import json
import time

import ms_api

# 1) 拉全量
items, total = [], 0
for page in range(1, 6):
    r = ms_api.list_collect_box(page, 500, "all")
    d = (r.get("data") or {}).get("data") or {}
    lst = d.get("detailList") or []
    total = d.get("total") or total
    items.extend(lst)
    if len(lst) < 500:
        break

skip = [i for i in items if str(i.get("status")) == "skip"]
keep = [i for i in items if str(i.get("status")) != "skip"]

print(f"总数 {len(items)}（接口 total={total}）| skip={len(skip)} | 保留={len(keep)}")
print("将删除的样例：")
for i in skip[:5]:
    print("  #", i.get("commonCollectBoxDetailId"), (i.get("title") or "")[:30], "|", i.get("reason"))
print("保留的：")
for i in keep[:6]:
    print("  #", i.get("commonCollectBoxDetailId"), (i.get("title") or "")[:30], "|", i.get("status"))

if not skip:
    raise SystemExit("没有 skip 记录")

ids = [int(i["commonCollectBoxDetailId"]) for i in skip]
res = ms_api.batch_delete_box(ids)
print("删除结果:", json.dumps(res, ensure_ascii=False))

time.sleep(1.2)
r = ms_api.list_collect_box(1, 10, "all")
d = (r.get("data") or {}).get("data") or {}
print("删除后 total:", d.get("total"))
