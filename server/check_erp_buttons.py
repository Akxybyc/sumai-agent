import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next((x for x in b.contexts[0].pages if "dianxiaobao.net" in x.url), None)
    pg.bring_to_front()
    data = pg.evaluate("""
    () => ({
      url: location.href,
      buttons: Array.from(document.querySelectorAll('button,a,span,div'))
        .filter(e => e.offsetParent)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 10 && /采集|开始|确定|提交/.test(t))
        .slice(0, 20),
      checked: Array.from(document.querySelectorAll('input[type=checkbox]')).map(e => e.checked),
      ta: Array.from(document.querySelectorAll('textarea')).map(e => (e.value || '').slice(0, 80))
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
