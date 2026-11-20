import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    links = pg.evaluate("""
    () => Array.from(document.querySelectorAll('a')).map(a => ({
      t: (a.innerText || '').replace(/\\s+/g, ' ').trim(), h: a.href
    })).filter(x => /插件|教程|下载|chrome|crx|ext/i.test(x.t + x.h)).slice(0, 10)
    """)
    print(json.dumps(links, ensure_ascii=False, indent=2))
