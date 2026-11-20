import json

from playwright.sync_api import sync_playwright

DOC_URL = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68"
PWD = "d8DUQdqH"

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = next((x for x in ctx.pages if "apifox" in x.url), None)
    if pg is None:
        pg = ctx.new_page()
        pg.set_viewport_size({"width": 1600, "height": 1000})
        pg.goto(DOC_URL, wait_until="domcontentloaded", timeout=60000)
    pg.bring_to_front()
    pg.wait_for_timeout(8000)
    # 若有密码输入框则填密码
    filled = pg.evaluate(f"""
    () => {{
      const inp = Array.from(document.querySelectorAll('input[type=password], input'))
        .find(e => e.offsetParent && (e.type === 'password' || /密码|password/i.test(e.placeholder || '')));
      if (!inp) return 'no-input';
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(inp, '{PWD}');
      inp.dispatchEvent(new Event('input', {{bubbles: true}}));
      return 'filled';
    }}
    """)
    print("pwd:", filled)
    pg.wait_for_timeout(500)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(6000)
    data = pg.evaluate("""
    () => {
      const t = (document.body.innerText || '').replace(/\\s+/g, ' ');
      // 侧边栏树
      const tree = Array.from(document.querySelectorAll('[class*="tree"] li, [class*="menu"] li, [class*="sidebar"] a, nav a'))
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 60);
      return {url: location.href, len: t.length, head: t.slice(0, 600), tail: t.slice(-100)};
    }
    """)
    (p2 := __import__("pathlib").Path("D:/WorkBuddy/sumai_agent/data/ms_api_doc.json")).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved ms_api_doc.json, items:", len(data["head"]))
    print(json.dumps(data["head"][:80], ensure_ascii=False, indent=1)[:1800])
