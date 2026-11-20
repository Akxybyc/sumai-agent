import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "goods-wait" in x.url)
    pg.bring_to_front()
    # 找店铺切换器
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const cur = Array.from(document.querySelectorAll('*'))
        .filter(e => vis(e) && (e.innerText || '').trim() === 'Shop1105202845 Store').length;
      const sels = Array.from(document.querySelectorAll('[class*="select"], [class*="dropdown"]'))
        .filter(vis).map(e => ({cls: String(e.className).slice(0,50), t: (e.innerText||'').replace(/\\s+/g,' ').slice(0,60)})).slice(0, 8);
      return {curMarks: cur, sels};
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:900])
