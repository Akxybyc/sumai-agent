import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc/collect_box" in x.url)
    data = pg.evaluate(
        """() => {
      const line = Array.from(document.querySelectorAll('.collect-box-table-base-line'))[0];
      if (!line) return 'no-line';
      const out = [];
      let el = line;
      for (let i = 0; i < 5 && el; i++) {
        el = el.parentElement;
        if (!el) break;
        out.push({cls: String(el.className).slice(0, 60), tag: el.tagName,
                  cbs: el.querySelectorAll('input[type=checkbox]').length,
                  len: (el.innerText || '').length});
      }
      return out;
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=2))
