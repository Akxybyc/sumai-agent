import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    btn = pg.get_by_text("认领", exact=True).first
    print("count:", pg.get_by_text("认领", exact=True).count())
    btn.click(timeout=5000)
    pg.wait_for_timeout(2500)
    data = pg.evaluate("""
    () => {
      const dlg = document.querySelector('[class*="modal"], [class*="dialog"], [role="dialog"]');
      const pick = (root) => ({
        text: root ? (root.innerText || '').replace(/\\s+/g, ' ').slice(0, 800) : '',
        selects: root ? Array.from(root.querySelectorAll('input')).map(e => e.placeholder || '').slice(0, 20) : [],
        buttons: root ? Array.from(root.querySelectorAll('button')).map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 20) : []
      });
      return {hasDialog: !!dlg, ...pick(dlg || document.body), url: location.href};
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2))
