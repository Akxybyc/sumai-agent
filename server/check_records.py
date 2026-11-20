import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    try:
        pg.get_by_text("采集记录", exact=True).first.click(timeout=4000)
        pg.wait_for_timeout(3000)
    except Exception as e:
        print("click fail", type(e).__name__)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 700)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
