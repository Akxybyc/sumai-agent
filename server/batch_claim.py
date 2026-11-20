import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "goods/common/copy" in x.url)
    pg.bring_to_front()

    # 勾选表格行（跳过表头全选）
    boxes = pg.locator("tbody input[type='checkbox']")
    print("row boxes:", boxes.count())
    for i in range(min(2, boxes.count())):
        try:
            boxes.nth(i).check(force=True, timeout=3000)
        except Exception as e:
            print("check fail", i, type(e).__name__)
    pg.wait_for_timeout(800)

    try:
        pg.get_by_text("批量认领", exact=True).first.click(timeout=5000)
        print("clicked 批量认领")
    except Exception as e:
        print("click fail", type(e).__name__)
    pg.wait_for_timeout(3000)

    data = pg.evaluate("""
    () => ({
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-700),
      buttons: Array.from(document.querySelectorAll('button')).filter(e => e.offsetParent)
        .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 30)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
