"""修正错位数据 + 按列头定位填写 SKU 行。"""
from playwright.sync_api import sync_playwright

FIX = {"重量": "0.45", "长": "8", "宽": "8", "高": "24"}


def type_into(pg, box, val):
    pg.mouse.click(box["x"] + 8, box["y"] + box["h"] / 2)
    pg.wait_for_timeout(200)
    pg.keyboard.press("Control+A")
    pg.keyboard.type(val, delay=30)
    pg.wait_for_timeout(200)


def by_placeholder(pg, ph):
    return pg.evaluate(
        """
        (ph) => { const e = Array.from(document.querySelectorAll('input'))
          .find(x => x.offsetParent && (x.placeholder || '') === ph);
          if (!e) return null; const r = e.getBoundingClientRect();
          return {x: r.x, y: r.y, w: r.width, h: r.height};
        }
        """,
        ph,
    )


def by_header(pg, header, nth=0):
    h = pg.get_by_text(header, exact=False).first
    h.scroll_into_view_if_needed()
    pg.wait_for_timeout(500)
    box = h.bounding_box()
    if not box:
        return None
    return pg.evaluate(
        """
        ({hx, hy, nth}) => {
          const cands = Array.from(document.querySelectorAll('input'))
            .filter(e => e.offsetParent)
            .map(e => { const r = e.getBoundingClientRect();
              return {x: r.x, y: r.y, w: r.width, h: r.height, cx: r.x + r.width / 2}; })
            .filter(b => b.y > hy + 5 && b.y < hy + 320 && Math.abs(b.cx - hx) < 160)
            .sort((a, b) => a.y - b.y);
          return cands[nth] || null;
        }
        """,
        {"hx": box["x"] + 20, "hy": box["y"], "nth": nth},
    )


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if "product_publish" in x.url)
    pg.bring_to_front()

    for ph, val in FIX.items():
        box = by_placeholder(pg, ph)
        if box:
            type_into(pg, box, val)
            print("fixed", ph, val)
        else:
            print("miss", ph)

    for header, val in [("供货价(CNY)", "20.93"), ("库存", "3666"), ("SKU编码", "ZNZ261001-01")]:
        box = by_header(pg, header)
        if box:
            type_into(pg, box, val)
            print("filled", header, val)
        else:
            print("miss", header)

    pg.wait_for_timeout(1500)
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ae_fixed.png")
    vals = pg.evaluate("""
    () => Array.from(document.querySelectorAll('input')).filter(e => e.offsetParent && e.value)
      .map(e => ({v: e.value.slice(0, 40), ph: e.placeholder || ''})).slice(0, 30)
    """)
    for v in vals:
        print(v)
