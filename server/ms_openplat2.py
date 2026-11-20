import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "91miaoshou" in x.url and "agent.html" not in x.url) \
        if any("agent.html" not in x.url and "91miaoshou" in x.url for c in b.contexts for x in c.pages) \
        else b.contexts[0].new_page()
    if "91miaoshou" not in pg.url or "agent.html" in pg.url:
        pg.goto("https://erp.91miaoshou.com/picture/index", wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(3000)
    r = pg.evaluate("""
    () => {
      const cands = Array.from(document.querySelectorAll('a,span,li'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '开放平台');
      for (const el of cands) {
        let anc = el, found = false;
        for (let k = 0; k < 6 && anc; k++) {
          anc = anc.parentElement;
          if (anc && (anc.innerText || '').includes('系统管理')) { found = true; break; }
        }
        if (found) { el.click(); return 'clicked-in-system-menu'; }
      }
      return cands.length ? 'clicked-fallback' : 'not-found';
    }
    """)
    print("open platform click:", r)
    pg.wait_for_timeout(5000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      title: document.title,
      text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 700)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
