"""验证：采集 → API 写英文标题/描述 → 认领 → 看全托管是否继承英文。"""
import json
import time
from pathlib import Path

import ms_api

DATA = Path("D:/WorkBuddy/sumai_agent/data")
fresh = json.loads((DATA / "fresh_link.json").read_text(encoding="utf-8"))
sid, url, cn_title, price = fresh
print(f"目标: {sid} | ¥{price} | {cn_title}")

# 1) 采集
r = ms_api.collect_by_links([url])
print("采集:", r.get("ok"), json.dumps(r.get("data"), ensure_ascii=False)[:160])

did = None
for _ in range(12):
    time.sleep(5)
    q = ms_api.list_collect_box(1, 5, "all", sid)
    lst = ((q.get("data") or {}).get("data") or {}).get("detailList") or []
    if lst and lst[0].get("status") == "success":
        did = lst[0].get("commonCollectBoxDetailId")
        break
    if lst and lst[0].get("commonCollectBoxDetailId"):
        did = lst[0].get("commonCollectBoxDetailId")
print("detailId:", did)

if not did:
    raise SystemExit("采集未成功，停止")

# 2) 读详情拿 ossMd5
q = ms_api.call("/open/v1/product/common_collect_box/common_collect_box/get_common_collect_box_detail",
                {"commonCollectBoxDetailId": did})
data = (q.get("data") or {}).get("data") or {}
det = data.get("editCommonCollectBoxDetail") or {}
md5 = data.get("ossMd5")
print("原标题:", (det.get("title") or "")[:40])
print("颜色属性名:", det.get("colorPropName"), "| price:", det.get("price"))

# 3) 翻成英文（妙手文本翻译）
tr = ms_api.translate_strings([det.get("title") or cn_title])
en = (tr.get("map") or {}).get(det.get("title") or cn_title) or ""
print("英文标题:", en[:90])

# 4) 写入英文（标题 + 颜色属性名）
body = {
    "commonCollectBoxDetailId": did,
    "ossMd5": md5,
    "editCommonCollectBoxDetail": {
        "title": en[:250],
        "price": det.get("price") or price or 1,
        "stock": min(int(det.get("stock") or 1000), 99999),
        "colorPropName": "Color",
        "notesText": (det.get("notesText") or "")[:2000],
    },
}
w = ms_api.call("/open/v1/product/common_collect_box/common_collect_box/edit_common_collect_box_detail", body)
print("写入:", w.get("ok"), (w.get("data") or {}).get("message"))

# 5) 回读确认
time.sleep(3)
q2 = ms_api.call("/open/v1/product/common_collect_box/common_collect_box/get_common_collect_box_detail",
                 {"commonCollectBoxDetailId": did})
d2 = ((q2.get("data") or {}).get("data") or {}).get("editCommonCollectBoxDetail") or {}
print("回读标题:", (d2.get("title") or "")[:90])
print("回读颜色名:", d2.get("colorPropName"))
(DATA / "verify_claim.json").write_text(json.dumps(
    {"detailId": did, "sid": sid, "en": en, "readback": d2.get("title")}, ensure_ascii=False),
    encoding="utf-8")
