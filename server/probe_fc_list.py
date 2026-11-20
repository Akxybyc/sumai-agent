import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    cands = [x for c in b.contexts for x in c.pages
             if "aliexpress_fc" in x.url and "collect_box" in x.url and "agent" not in x.url]
    print("候选页:", [c.url[-45:] for c in cands])
    if not cands:
        raise SystemExit("没找到全托管采集箱页面，请先在妙手打开它")
    pg = cands[0]
    pg.bring_to_front()
    pg.wait_for_timeout(2000)
    d = pg.evaluate(
        """() => {
      const rows = [...document.querySelectorAll('.jx-pro-virtual-table__row')];
      const hasEdit = (r) => [...r.querySelectorAll('a,span,button,div')]
        .some(e => (e.innerText || '').trim() === '编辑');
      return {
        rows: rows.length,
        editRows: rows.filter(hasEdit).length,
        first: (rows[0] || {}).innerText ? rows[0].innerText.split('\\n').slice(0, 8) : [],
        buttons: [...document.querySelectorAll('button')].filter(e => e.offsetParent)
          .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 14),
      };
    }"""
    )
    print(json.dumps(d, ensure_ascii=False, indent=1)[:800])
