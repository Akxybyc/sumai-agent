import json
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """
() => {
  const out = [];
  const els = Array.from(document.querySelectorAll('input, textarea, [contenteditable="true"]'));
  els.forEach((e, i) => {
    if (!e.offsetParent) return;
    const r = e.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return;
    let p = e, ctx = '';
    for (let k = 0; k < 5 && p; k++) {
      p = p.parentElement;
      if (!p) break;
      const t = (p.innerText || '').replace(/\\s+/g, ' ').trim();
      if (t && t.length < 120) { ctx = t; break; }
    }
    out.push({
      i, tag: e.tagName, ph: e.placeholder || '', cls: String(e.className || '').slice(0, 50),
      x: Math.round(r.x), y: Math.round(r.y), ctx
    });
  });
  return out.slice(0, 90);
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "product_publish" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.goto("https://csp.aliexpress.com/ait/cn_ams/item_choice/product_publish?from=SELF&channelId=2590500", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
    pg.bring_to_front()
    pg.wait_for_timeout(1500)
    data = pg.evaluate(JS)
    Path("D:/WorkBuddy/sumai_agent/data/ae_inputs_map.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("ok", len(data))
