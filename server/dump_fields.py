"""导出速卖通发布表单字段结构（标签/类型/必填/占位符/所属区块）。

只读：不填、不点保存。
"""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path("D:/WorkBuddy/sumai_agent/data")
PUB_URL = ("https://csp.aliexpress.com/ait/cn_ams/item_choice/product_publish"
           "?from=SELF&channelId=2590500")

JS = r"""
() => {
  const vis = (e) => e.offsetParent !== null;
  const clean = (t) => (t || '').replace(/\s+/g, ' ').trim();

  // 反向找最近的短文本作为标签
  function labelOf(el) {
    let p = el, best = '';
    for (let i = 0; i < 6 && p; i++) {
      p = p.parentElement;
      if (!p) break;
      const t = clean(p.innerText);
      if (t && t.length <= 40) { best = t; break; }
    }
    if (!best) {
      const l = el.getAttribute('aria-label') || '';
      if (l) best = l;
    }
    return best;
  }

  const out = [];
  const nodes = Array.from(document.querySelectorAll('input, textarea, select'));
  nodes.forEach((el, i) => {
    if (!vis(el)) return;
    const r = el.getBoundingClientRect();
    if (r.width < 10 || r.height < 8) return;
    const label = labelOf(el);
    out.push({
      idx: i,
      tag: el.tagName.toLowerCase(),
      type: (el.type || '').toLowerCase(),
      placeholder: el.placeholder || '',
      label,
      required: label.includes('*'),
      value: (el.value || '').slice(0, 30),
      cls: String(el.className || '').slice(0, 40),
      x: Math.round(r.x), y: Math.round(r.y)
    });
  });

  // 尝试抓区块标题（h3/h4/带 section 类的短文本）
  const sections = Array.from(document.querySelectorAll('h3, h4, [class*="section-title"], [class*="card-title"]'))
    .filter(vis).map(e => clean(e.innerText)).filter(t => t && t.length <= 20).slice(0, 30);

  return {
    url: location.href,
    title: document.title,
    count: out.length,
    fields: out,
    sections,
    bodyLen: (document.body.innerText || '').length
  };
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "product_publish" in x.url), None)
    opened = False
    if pg is None:
        pg = ctx.new_page()
        pg.set_viewport_size({"width": 1440, "height": 950})
        pg.goto(PUB_URL, wait_until="domcontentloaded", timeout=60000)
        opened = True
    pg.bring_to_front()
    for _ in range(3):
        pg.wait_for_timeout(3000)
    data = pg.evaluate(JS)
    data["opened_new_tab"] = opened
    (DATA / "ae_fields.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print("url:", data["url"])
    print("fields:", data["count"])
    print("sections:", " | ".join(data["sections"][:12]))
    labeled = sum(1 for f in data["fields"] if f["label"])
    required = sum(1 for f in data["fields"] if f["required"])
    print(f"labels: {labeled}/{data['count']}  required: {required}")
    for f in data["fields"][:15]:
        print(f"  [{f['tag']}/{f['type']}] req={f['required']} label='{f['label'][:24]}' ph='{f['placeholder'][:18]}'")
