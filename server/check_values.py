from playwright.sync_api import sync_playwright

JS = """
() => {
  const rows = [];
  document.querySelectorAll('input').forEach(e => {
    if (!e.offsetParent) return;
    if (!e.value || e.type === 'checkbox' || e.type === 'radio') return;
    let p = e, ctx = '';
    for (let k = 0; k < 4 && p; k++) { p = p.parentElement; if (!p) break;
      const t = (p.innerText || '').replace(/\\s+/g, ' ').trim();
      if (t && t.length < 80) { ctx = t; break; } }
    rows.push({v: e.value.slice(0, 60), ph: e.placeholder || '', ctx});
  });
  return rows.slice(0, 40);
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for x in b.contexts[0].pages if "product_publish" in x.url)
    pg.bring_to_front()
    for r in pg.evaluate(JS):
        print(r)
