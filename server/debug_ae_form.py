import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data")

JS = """
() => ({
  url: location.href,
  title: document.title,
  text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 800),
  inputs: Array.from(document.querySelectorAll('input,select,textarea'))
    .filter(e => e.offsetParent).map(e => ({
      tag: e.tagName, type: e.type || '', ph: e.placeholder || '',
      label: (e.closest('label')?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 30)
    })).slice(0, 40),
  iframes: Array.from(document.querySelectorAll('iframe')).map(f => f.src)
})
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "product_publish" in x.url), ctx.pages[-1])
    pg.bring_to_front()
    for _ in range(3):
        pg.wait_for_timeout(3000)
        try:
            pg.mouse.wheel(0, 600)
        except Exception:
            pass
    pg.wait_for_timeout(3000)
    data = pg.evaluate(JS)
    frames = []
    for fr in pg.frames:
        try:
            d = fr.evaluate("() => ({url: location.href, text: (document.body.innerText||'').replace(/\\s+/g,' ').slice(0,300), inputs: Array.from(document.querySelectorAll('input,select,textarea')).filter(e=>e.offsetParent).length})")
            frames.append(d)
        except Exception:
            continue
    data["frames"] = frames
    (OUT / "ae_form_ready.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    pg.screenshot(path=str(OUT / "ae_form_ready.png"))
    print("ok", len(data["inputs"]), "frames", len(frames))
