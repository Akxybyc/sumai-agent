import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc" in x.url and "collect_box" in x.url)
    pg.bring_to_front()
    data = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      // 找包含「类目&属性」的区块
      const anchor = Array.from(document.querySelectorAll('*'))
        .filter(e => vis(e) && (e.innerText || '').trim() === '类目&属性')[0];
      if (!anchor) return {found: false};
      let box = anchor;
      for (let i = 0; i < 6 && box.parentElement; i++) box = box.parentElement;
      const txt = (box.innerText || '').replace(/\\s+/g, ' ');
      // 属性行：label + 控件
      const rows = Array.from(box.querySelectorAll('label, [class*="label"], [class*="form-item"]'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 40);
      const inputs = Array.from(box.querySelectorAll('input, textarea, [class*="select"]'))
        .filter(vis).length;
      return {found: true, len: (box.innerText || '').length,
              sample: txt.slice(0, 1200),
              rows: Array.from(new Set(rows)).slice(0, 40), inputs};
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=1)[:2500])
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ms_edit_attrs.png", full_page=True)
