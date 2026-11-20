import json
import time

from playwright.sync_api import sync_playwright

FIELDS = ["产地", "材质", "高关注化学品", "功能", "特性", "风格", "固定方式", "外形因素"]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc" in x.url and "collect_box" in x.url)
    pg.bring_to_front()
    out = {}

    for f in FIELDS:
        # 找到该字段对应的选择框（label 文本 → 同容器内 select）
        clicked = pg.evaluate(
            """(name) => {
          const vis = e => e.offsetParent !== null;
          const lbl = Array.from(document.querySelectorAll('label, [class*="label"], span, div'))
            .filter(e => vis(e) && (e.innerText || '').includes(name) && (e.innerText || '').length < 40)
            .sort((a, b) => a.innerText.length - b.innerText.length)[0];
          if (!lbl) return 'no-label';
          let box = lbl;
          for (let i = 0; i < 4 && box.parentElement; i++) {
            box = box.parentElement;
            const sel = box.querySelector('[class*="select"], input[class*="select"], [class*="selector"]');
            if (sel) { sel.click(); return 'clicked'; }
          }
          return 'no-select';
        }""",
            f,
        )
        time.sleep(1.2)
        opts = pg.evaluate(
            """() => {
          const vis = e => e.offsetParent !== null;
          return Array.from(document.querySelectorAll('[class*="dropdown"] li, [class*="option"], [class*="item"]'))
            .filter(vis)
            .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
            .filter(t => t && t.length <= 30)
            .slice(0, 30);
        }"""
        )
        out[f] = {"click": clicked, "options": list(dict.fromkeys(opts))[:20]}
        pg.keyboard.press("Escape")
        time.sleep(0.4)

    print(json.dumps(out, ensure_ascii=False, indent=1)[:2500])
