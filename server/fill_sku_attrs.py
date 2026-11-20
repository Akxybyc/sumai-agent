"""选择颜色主色系与容量，生成 SKU 行。"""
import json

from playwright.sync_api import sync_playwright

COLORS = ["粉色", "黑色", "绿色", "紫色", "白色"]
CAP = "600ml"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if "product_publish" in x.url)
    pg.bring_to_front()
    log = []

    # 颜色：点击占位文本后逐个别名输入
    try:
        ph = pg.get_by_text("选择主色系", exact=True).first
        ph.scroll_into_view_if_needed()
        ph.click(timeout=5000)
        pg.wait_for_timeout(600)
        for c in COLORS:
            pg.keyboard.type(c, delay=40)
            pg.wait_for_timeout(400)
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(300)
        log.append(f"colors={len(COLORS)}")
    except Exception as e:
        log.append(f"color_fail:{type(e).__name__}")

    # 容量
    try:
        cap_box = pg.get_by_text("容量", exact=True).first
        cap_box.scroll_into_view_if_needed()
        pg.wait_for_timeout(400)
        b0 = cap_box.bounding_box()
        target = pg.evaluate(
            """
            ({x, y}) => { const els = Array.from(document.querySelectorAll('input, [contenteditable="true"]'))
              .filter(e => e.offsetParent).map(e => { const r = e.getBoundingClientRect();
                return {x: r.x, y: r.y, w: r.width, h: r.height}; })
              .filter(b => b.y > y - 10 && b.y < y + 70 && b.x > x)
              .sort((a, b) => a.x - b.x);
              return els[0] || null; }
            """,
            {"x": b0["x"], "y": b0["y"]},
        )
        if target:
            pg.mouse.click(target["x"] + 8, target["y"] + target["h"] / 2)
            pg.wait_for_timeout(300)
            pg.keyboard.type(CAP, delay=40)
            pg.wait_for_timeout(500)
            pg.keyboard.press("Enter")
            log.append("cap_ok")
        else:
            log.append("cap_miss")
    except Exception as e:
        log.append(f"cap_fail:{type(e).__name__}")

    pg.wait_for_timeout(2500)
    state = pg.evaluate("""
    () => ({
      text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 400),
      inputs: Array.from(document.querySelectorAll('input')).filter(e => e.offsetParent).length,
      withPh: Array.from(document.querySelectorAll('input')).filter(e => e.offsetParent && e.placeholder)
        .map(e => e.placeholder).slice(0, 20)
    })
    """)
    print(json.dumps({"log": log, "state": state}, ensure_ascii=False))
