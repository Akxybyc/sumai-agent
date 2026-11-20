import time

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    pg.reload(wait_until="domcontentloaded")
    pg.wait_for_timeout(6000)
    print("reloaded", pg.url)
