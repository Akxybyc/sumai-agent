import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [x for c in b.contexts for x in c.pages if "91miaoshou.com" in x.url and "agent.html" not in x.url]
    if not pages:
        raise SystemExit("没有妙手页面")
    pg = pages[0]
    pg.bring_to_front()

    # 进采集箱 → 编辑
    if "collect_box" not in pg.url:
        for label in ("速卖通全托管",):
            pg.evaluate(
                """(l) => {
              const els = Array.from(document.querySelectorAll('a, span, li, div'))
                .filter(e => e.offsetParent && (e.innerText || '').trim() === l)
                .sort((a, b) => a.innerText.length - b.innerText.length);
              if (els.length) els[0].click();
            }""",
                label,
            )
            pg.wait_for_timeout(4000)
    if not pg.evaluate("() => !!document.querySelector('.category-attribute-list')"):
        pg.evaluate(
            """() => {
          const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
          for (const r of rows) {
            const btn = Array.from(r.querySelectorAll('a, span, button, div'))
              .find(e => (e.innerText || '').trim() === '编辑');
            if (btn) { btn.click(); return true; }
          }
        }"""
        )
        pg.wait_for_timeout(7000)

    data = pg.evaluate(
        """() => {
      const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
      // 找“自定义属性”标题
      const heads = Array.from(document.querySelectorAll('*'))
        .filter(e => vis(e) && (e.innerText || '').trim() === '自定义属性' && e.children.length === 0);
      const head = heads[heads.length - 1];
      if (!head) return {found: false};
      let box = head;
      for (let i = 0; i < 4 && box.parentElement; i++) box = box.parentElement;
      const rows = Array.from(box.querySelectorAll('[class*="row"], tr, li')).filter(vis).slice(0, 6);
      const inputs = Array.from(box.querySelectorAll('input, textarea, [contenteditable="true"]')).filter(vis);
      return {
        found: true,
        boxCls: String(box.className).slice(0, 60),
        rowCount: rows.length,
        rowSamples: rows.slice(0, 3).map(r => ({cls: String(r.className).slice(0, 40),
                                                t: (r.innerText || '').replace(/\\s+/g, ' ').slice(0, 60)})),
        inputCount: inputs.length,
        inputSamples: inputs.slice(0, 5).map(i => ({tag: i.tagName, cls: String(i.className).slice(0, 30),
                                                    val: (i.value || '').slice(0, 20)})),
        html: box.outerHTML.slice(0, 700)
      };
    }"""
    )
    print(json.dumps(data, ensure_ascii=False, indent=1)[:2000])
