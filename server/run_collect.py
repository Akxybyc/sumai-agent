"""直接执行：关弹窗 → 贴链接 → 开始采集（不依赖后端重启）。"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
drafts = json.loads((DATA / "drafts.json").read_text(encoding="utf-8"))
links = [d.get("source_url") for d in drafts if d.get("source_url")]
print("links:", links)

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    for t in ("取消", "关闭"):
        try:
            btn = pg.get_by_text(t, exact=True).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=2500)
                print("closed", t)
                pg.wait_for_timeout(800)
                break
        except Exception:
            pass

    tas = pg.locator("textarea")
    filled = False
    for i in range(tas.count()):
        box = tas.nth(i)
        if not box.is_visible():
            continue
        box.click(timeout=5000)
        box.fill("\n".join(links))
        filled = True
        print("filled textarea", i)
        break
    if not filled:
        raise SystemExit("no visible textarea")

    pg.wait_for_timeout(600)
    for text in ("开始采集",):
        btn = pg.get_by_text(text, exact=True).first
        if btn.count() > 0 and btn.is_visible():
            btn.click(timeout=5000)
            print("clicked", text)
    pg.wait_for_timeout(10000)
    print("url:", pg.url)
    body = pg.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ')")
    print(body[-400:])
