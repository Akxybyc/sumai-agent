import json

from playwright.sync_api import sync_playwright

CLICK_JS = """
() => {
  const boxes = Array.from(document.querySelectorAll('tbody input[type=checkbox]')).slice(0, 2);
  boxes.forEach(b => { b.click(); });
  const btn = Array.from(document.querySelectorAll('button, span, a'))
    .find(e => (e.innerText || '').trim() === '批量认领');
  const clicked = !!btn;
  if (btn) btn.click();
  return {boxes: boxes.length, clicked, text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-300)};
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "goods/common/copy" in x.url)
    pg.bring_to_front()
    pg.wait_for_timeout(500)
    print(json.dumps(pg.evaluate(CLICK_JS), ensure_ascii=False, indent=2))
    pg.wait_for_timeout(3000)
    data = pg.evaluate("""
    () => ({
      tail: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(-600),
      buttons: Array.from(document.querySelectorAll('button')).filter(e => e.offsetParent)
        .map(e => (e.innerText || '').trim()).filter(Boolean).slice(0, 25)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
