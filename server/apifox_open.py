import json
import sys

from playwright.sync_api import sync_playwright

URL = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68"
PWD = "d8DUQdqH"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3500)

    # 输入密码
    try:
        inp = pg.locator('input[type="password"]').first
        inp.fill(PWD, timeout=8000)
        pg.wait_for_timeout(300)
        for txt in ("访问文档", "进入", "确定", "提交"):
            btn = pg.get_by_text(txt, exact=True)
            if btn.count():
                btn.first.click()
                break
        pg.wait_for_timeout(6000)
    except Exception as e:
        print("pwd step:", type(e).__name__, str(e)[:120])

    print("url:", pg.url)
    body = pg.evaluate("() => document.body.innerText") or ""
    print("text head:", body.replace("\n", " ")[:500])

    links = pg.evaluate(
        """() => Array.from(document.querySelectorAll('a')).map(a => ({t: (a.innerText||'').trim().slice(0,40), h: a.href})).filter(o => o.t)"""
    )
    print("links:", json.dumps(links[:40], ensure_ascii=False, indent=1)[:1500])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/apifox_doc.png", full_page=False)
