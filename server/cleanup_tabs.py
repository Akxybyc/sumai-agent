"""清理多余标签页，只保留发布商品页，释放内存。"""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    keep = []
    for pg in ctx.pages:
        url = pg.url
        if "product_publish" in url:
            keep.append(pg)
            continue
        try:
            pg.close()
        except Exception:
            pass
    print("kept:", [x.url for x in keep])
    if not keep:
        np = ctx.new_page()
        np.goto("https://csp.aliexpress.com/ait/cn_ams/item_choice/product_publish?from=SELF&channelId=2590500",
                wait_until="domcontentloaded", timeout=60000)
        np.wait_for_timeout(6000)
        print("opened:", np.url)
