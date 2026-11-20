import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next((x for x in b.contexts[0].pages if "dianxiaobao.net" in x.url), None)
    if pg is None:
        print("no page")
        raise SystemExit
    pg.bring_to_front()
    data = pg.evaluate("""
    () => {
      const ta = Array.from(document.querySelectorAll('textarea')).filter(e => e.offsetParent);
      return {
        url: location.href,
        title: document.title,
        textareas: ta.map(e => ({ph: e.placeholder || '', val: (e.value || '').slice(0, 300)})),
        text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 400)
      };
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
