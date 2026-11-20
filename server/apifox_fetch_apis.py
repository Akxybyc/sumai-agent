import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68/"
TARGETS = {
    "collect_by_link": "api-446814581",
    "box_list": "api-446814582",
    "ai_attr_match": "api-482189161",
    "ai_category": "api-482189162",
    "product_translate": "api-482189160",
    "publish": "api-446814595",
    "category_attrs": "api-446814589",
}
OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_docs")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "s.apifox.cn" in x.url)

    for name, aid in TARGETS.items():
        pg.goto(ROOT + aid, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4200)
        txt = pg.evaluate("() => document.body.innerText") or ""
        # 只保留接口主体（去掉左侧目录）
        i = txt.find("复制页面")
        body = txt[i:] if i > 0 else txt
        (OUT / f"{name}.txt").write_text(body, encoding="utf-8")
        m = re.search(r"(/open/v1/\S+)", body)
        print(f"{name:18} {aid}  path={m.group(1) if m else '?'}  len={len(body)}")
