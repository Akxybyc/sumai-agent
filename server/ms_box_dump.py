import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc/collect_box" in x.url)
    pg.bring_to_front()
    pg.wait_for_timeout(3000)
    data = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      const tables = Array.from(document.querySelectorAll('table')).map(t => ({
        cls: String(t.className).slice(0, 40),
        rows: t.querySelectorAll('tr').length
      }));
      const tbodyRows = document.querySelectorAll('tbody tr').length;
      // 找所有含“货源”的小块
      const blocks = Array.from(document.querySelectorAll('div, li, tr'))
        .filter(e => vis(e) && /货源[：:]/.test(e.innerText || ''))
        .map(e => ({tag: e.tagName, cls: String(e.className).slice(0, 40),
                    t: (e.innerText || '').replace(/\\s+/g, ' ').slice(0, 100)}))
        .sort((a, b) => a.t.length - b.t.length).slice(0, 6);
      return {url: location.href, tables, tbodyRows, blocks,
              bodyTail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-400)};
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])
