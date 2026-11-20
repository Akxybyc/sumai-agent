import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next((x for x in b.contexts[0].pages if "accio.com" in x.url), None)
    if pg is None:
        pg = b.contexts[0].new_page()
        pg.goto("https://www.accio.com/", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
    links = pg.evaluate("""
    () => Array.from(document.querySelectorAll('a')).map(a => ({
      t: (a.innerText || '').replace(/\\s+/g, ' ').trim(),
      h: a.href
    })).filter(x => x.h && /渠道|平台|自动化|文档|帮助|help|docs|skill/i.test(x.t + x.h)).slice(0, 30)
    """)
    print(json.dumps(links, ensure_ascii=False, indent=2))
    pg.close()
