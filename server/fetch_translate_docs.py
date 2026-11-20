import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68/"
IDS = {
    "pub1": "api-446814595", "pub2": "api-468724006", "pub3": "api-511668107",
    "claim2": "api-471545323", "claim3": "api-446814594",
    "attr": "api-446814589",
}
OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_docs")
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next((x for c in b.contexts for x in c.pages if "s.apifox.cn" in x.url), None)
    if pg is None:
        pg = b.contexts[0].new_page()
    for name, aid in IDS.items():
        pg.goto(ROOT + aid, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(3500)
        t = pg.evaluate("() => document.body.innerText") or ""
        i = t.find("复制页面")
        body = t[i:] if i > 0 else t
        m = re.search(r"(/open/v1/\S+)", body)
        (OUT / f"{name}.txt").write_text(body, encoding="utf-8")
        print(f"{name:22} path={m.group(1) if m else '?'} len={len(body)}")
