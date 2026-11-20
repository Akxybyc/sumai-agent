import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_tree.json")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "apifox" in x.url)
    pg.bring_to_front()
    # 展开左侧「商品」分组
    r = pg.evaluate("""
    () => {
      const els = Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '商品'
                     && e.querySelector('*') === null || (e.innerText||'').trim()==='商品');
      const el = els.sort((a,b)=>a.innerText.length-b.innerText.length)[0];
      if (el) { el.click(); return 'clicked'; }
      return 'not-found';
    }
    """)
    print("expand 商品:", r)
    pg.wait_for_timeout(2000)
    # 点几次展开所有分组
    for grp in ("包裹", "采购", "仓储", "货源账号"):
        pg.evaluate(f"""
        () => {{
          const el = Array.from(document.querySelectorAll('*'))
            .filter(e => e.offsetParent && (e.innerText||'').trim() === '{grp}')
            .sort((a,b)=>a.innerText.length-b.innerText.length)[0];
          if (el) el.click();
        }}
        """)
        pg.wait_for_timeout(1200)
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const items = Array.from(document.querySelectorAll('a, span, div'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t.includes('/open/') || /(v1|v2)\\//.test(t));
      return {url: location.href, uniq: Array.from(new Set(items))};
    }
    """)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    u = data["uniq"]
    print("endpoint-like items:", len(u))
    for t in u[:80]:
        print("-", t[:100])
