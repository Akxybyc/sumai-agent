"""调试脚本：打印 1688 搜索结果卡片的祖先链，用来确定提取规则。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """
() => {
  const res = [];
  const links = Array.from(document.querySelectorAll('a[href*="offer/"]'))
    .filter(a => /offer\\/\\d+\\.html/.test(a.href)).slice(0, 6);
  for (const a of links) {
    const chain = [];
    let n = a;
    for (let i = 0; i < 8 && n.parentElement; i++) {
      n = n.parentElement;
      chain.push({
        tag: n.tagName,
        cls: (n.className || '').toString().slice(0, 100),
        links: n.querySelectorAll('a[href*="offer/"]').length,
        imgs: n.querySelectorAll('img').length,
        len: (n.innerText || '').replace(/\\s+/g, ' ').trim().length,
        text: (n.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 120)
      });
    }
    res.push({href: a.href, anchor: (a.getAttribute('title') || '').slice(0, 60), chain});
  }
  return res;
}
"""


def main(keyword: str = "保温杯") -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "dom_debug.json"
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            from urllib.parse import quote
            url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(keyword.encode('gbk'))}"
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            data = page.evaluate(JS)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"saved {out} items={len(data)}")
        finally:
            page.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "保温杯")
