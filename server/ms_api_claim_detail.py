import json
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_claim.json")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "apifox" in x.url)
    pg.bring_to_front()
    try:
        pg.locator("text=认领到平台采集箱").first.click(timeout=5000)
        print("clicked")
    except Exception as e:
        print("fail", type(e).__name__)
    pg.wait_for_timeout(3000)
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const main = (document.querySelector('main') || document.body).innerText || '';
      return {url: location.href, text: main.replace(/\\s+/g, ' ').slice(0, 3500)};
    }
    """)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(data["text"][:3000])
