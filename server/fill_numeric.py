"""按标签定位同排输入框并填入数值（供货价/库存/SKU编码/重量）。"""
from playwright.sync_api import sync_playwright

VALUES = {
    "供货价": ["20.93", "3666", "ZNZ261001-01"],
    "重量": ["0.45"],
}


def near_inputs(pg, label, count):
    lab = pg.get_by_text(label, exact=False).first
    lab.scroll_into_view_if_needed()
    pg.wait_for_timeout(600)
    box = lab.bounding_box()
    if not box:
        return []
    boxes = pg.evaluate(
        """
        ({lx, ly}) => Array.from(document.querySelectorAll('input'))
          .filter(e => e.offsetParent)
          .map(e => { const r = e.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height}; })
          .filter(b => b.y > ly - 20 && b.y < ly + 90 && b.x > lx - 40 && b.w > 20)
          .sort((a, b) => a.x - b.x)
          .slice(0, 8)
        """,
        {"lx": box["x"], "ly": box["y"]},
    )
    return boxes[:count]


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "product_publish" in x.url), None)
    if pg is None:
        raise SystemExit("no publish page")
    pg.bring_to_front()

    for label, vals in VALUES.items():
        boxes = near_inputs(pg, label, len(vals))
        print(label, "found", len(boxes))
        for box, val in zip(boxes, vals):
            pg.mouse.click(box["x"] + 6, box["y"] + box["h"] / 2)
            pg.wait_for_timeout(250)
            pg.keyboard.press("Control+A")
            pg.keyboard.type(val, delay=30)
            pg.wait_for_timeout(250)
        pg.wait_for_timeout(800)

    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ae_numbers.png")
    vals = pg.evaluate("""
    () => Array.from(document.querySelectorAll('input')).filter(e => e.offsetParent && e.value)
      .map(e => e.value).slice(0, 20)
    """)
    print("filled:", vals)
