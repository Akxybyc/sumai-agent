"""抓取妙手 API 文档的完整目录（含分组名），用于判断哪些接口可用。"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

DOC = "https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68"
OUT = Path("D:/WorkBuddy/sumai_agent/data/ms_api_tree.json")

JS = """() => {
  const out = [];
  const nodes = document.querySelectorAll('[class*=catalog] *, [class*=Catalog] *');
  const items = [];
  document.querySelectorAll('a[href*="api-"], a[href*="doc-"]').forEach(a => {
    const t = (a.innerText || '').trim().replace(/\\s+/g, ' ');
    if (!t) return;
    const r = a.getBoundingClientRect();
    items.push({ t, href: a.href, top: Math.round(r.top) });
  });
  return items;
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next((x for c in b.contexts for x in c.pages if "s.apifox.cn" in x.url), None)
    if pg is None:
        pg = b.contexts[0].new_page()

    # 可能要先输密码
    pg.goto(DOC, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(3000)
    body = pg.evaluate("() => document.body.innerText") or ""
    if "密码" in body[:400] and "输入" in body[:400]:
        inp = pg.query_selector("input")
        if inp:
            inp.fill("d8DUQdqH")
            pg.keyboard.press("Enter")
            pg.wait_for_timeout(4000)
            print("已尝试输入访问密码")

    # 展开全部目录
    for _ in range(6):
        pg.evaluate("""() => {
          document.querySelectorAll('[class*=tree] [class*=arrow], [class*=expand], [class*=caret]')
            .forEach(e => { try { e.click(); } catch (_) {} });
        }""")
        pg.wait_for_timeout(800)

    # 滚动侧栏加载全部
    for _ in range(12):
        pg.evaluate("""() => {
          const el = document.querySelector('[class*=catalog], [class*=sidebar], aside');
          if (el) el.scrollTop = el.scrollHeight;
        }""")
        pg.wait_for_timeout(600)

    items = pg.evaluate(JS)
    seen, uniq = set(), []
    for it in items:
        if it["href"] in seen:
            continue
        seen.add(it["href"])
        uniq.append(it)
    OUT.write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding="utf-8")
    print("抓到目录项:", len(uniq))
