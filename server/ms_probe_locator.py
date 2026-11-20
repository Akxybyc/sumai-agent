from playwright.sync_api import sync_playwright

LINK = "https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy"
PAYLOAD = "https://detail.1688.com/offer/979658766024.html$$Phone Stand Holder"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    pg = pages[0]
    pg.bring_to_front()
    pg.set_viewport_size({"width": 1440, "height": 950})
    pg.goto(LINK, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)

    ta = pg.locator("textarea").first
    ta.click()
    ta.type(PAYLOAD, delay=6)
    pg.wait_for_timeout(1000)
    print("输入长度:", pg.evaluate("() => document.querySelector('textarea').value.length"))

    btn = pg.locator("button", has_text="采集并自动认领").last
    print("按钮数:", pg.locator("button", has_text="采集并自动认领").count())
    print("可见:", btn.is_visible(), "启用:", btn.is_enabled())
    try:
        btn.scroll_into_view_if_needed()
        btn.click(timeout=8000)
        print("locator.click 成功")
    except Exception as e:
        print("click 异常:", type(e).__name__, str(e)[:220])

    pg.wait_for_timeout(5000)
    print("结果:", pg.evaluate("""() => {
      const ta = document.querySelector('textarea');
      const d = Array.from(document.querySelectorAll('[class*="dialog"],[class*="message"]'))
        .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g,' ').trim()).filter(Boolean).slice(0,3);
      return {taLen: ta.value.length, dlg: d};
    }"""))
