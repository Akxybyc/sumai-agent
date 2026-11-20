import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68/"
IDS = {
    "认领_446814587": "api-446814587",
    "认领预发布_446814594": "api-446814594",
    "认领预发布_471545323": "api-471545323",
    "认领预发布_477347603": "api-477347603",
    "发布_446814595": "api-446814595",
    "发布_468724006": "api-468724006",
    "发布_468726294": "api-468726294",
    "发布_474774631": "api-474774631",
    "发布_482757484": "api-482757484",
    "发布_480434554": "api-480434554",
    "任务_480434555": "api-480434555",
    "类目_471545330": "api-471545330",
    "类目_474774625": "api-474774625",
    "类目_484103119": "api-484103119",
    "类目树_516157446": "api-516157446",
}
OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_docs")
rows = []

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "s.apifox.cn" in x.url)
    for name, aid in IDS.items():
        try:
            pg.goto(ROOT + aid, wait_until="domcontentloaded", timeout=45000)
            pg.wait_for_timeout(3200)
            txt = pg.evaluate("() => document.body.innerText") or ""
            m = re.search(r"(/open/v1/\S+)", txt)
            path = m.group(1) if m else "?"
            (OUT / f"{name}.txt").write_text(txt, encoding="utf-8")
            rows.append({"name": name, "path": path})
            print(f"{name:24} {path}")
        except Exception as e:
            print(f"{name:24} ERR {type(e).__name__}")

Path("D:/WorkBuddy/sumai_agent/data/ms_publish_paths.json").write_text(
    json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
