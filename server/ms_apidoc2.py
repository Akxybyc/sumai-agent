import json
from pathlib import Path

from playwright.sync_api import sync_playwright

DOC_URL = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68"
PWD = "d8DUQdqH"
OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_doc.json")

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "apifox" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.goto(DOC_URL, wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(5000)
    try:
        inp = pg.locator("input:visible").first
        inp.click(timeout=4000)
        inp.fill(PWD)
        pg.wait_for_timeout(300)
        pg.keyboard.press("Enter")
        print("password typed")
    except Exception as e:
        print("input fail:", type(e).__name__)
    pg.wait_for_timeout(1000)
    try:
        pg.get_by_text("访问文档", exact=True).first.click(timeout=4000)
        print("clicked 访问文档")
    except Exception as e:
        print("btn fail:", type(e).__name__)
    pg.wait_for_timeout(9000)
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const items = Array.from(document.querySelectorAll('a, span, div'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && 2 < t.length <= 70)
      return {url: location.href, uniq: Array.from(new Set(items)).slice(0, 500)};
    }
    """)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    uniq = data["uniq"]
    print("uniq items:", len(uniq))
    keys = ("采集", "刊登", "发布", "认领", "商品", "product", "collect", "publish")
    kw = [t for t in uniq if any(k in t.lower() for k in keys)][:60]
    print(json.dumps(kw, ensure_ascii=False, indent=1)[:1500])
