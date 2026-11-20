import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next((x for c in b.contexts for x in c.pages if "ufuwu.1688.com" in x.url), None)
    if pg is None:
        print("tab gone")
        raise SystemExit
    pg.bring_to_front()
    pg.wait_for_timeout(4000)
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      return {
        url: location.href.slice(0, 120),
        title: document.title,
        buttons: Array.from(document.querySelectorAll('button, a, [class*="btn"]'))
          .filter(vis)
          .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
          .filter(t => t && t.length <= 20).slice(0, 30),
        text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 600),
        frames: Array.from(document.querySelectorAll('iframe')).map(f => f.src.slice(0, 100))
      };
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1800])
    for i, f in enumerate(pg.frames):
        if f != pg.main_frame:
            try:
                t = f.evaluate("() => (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').slice(0, 300)")
                btns = f.eval_on_selector_all("button, a", "els => els.filter(e=>e.offsetParent).map(e=>(e.innerText||'').trim()).filter(Boolean).slice(0,15)")
                print(f"--- frame {i}: {f.url[:80]}")
                print("text:", t[:250])
                print("btns:", btns)
            except Exception as e:
                print(f"frame {i} err", type(e).__name__)
