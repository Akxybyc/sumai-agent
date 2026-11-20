"""调试：检查商品链接自身的文本长度与结构。"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """
() => {
  const arr = Array.from(document.querySelectorAll('a[href*="offer/"]'))
    .filter(a => /offer\\/\\d+\\.html/.test(a.href));
  return {
    count: arr.length,
    url: location.href,
    title: document.title,
    bodyLen: document.body ? (document.body.innerText || '').length : 0,
    bodySnippet: document.body ? (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 200) : '',
    samples: arr.slice(0, 5).map(a => ({
      textLen: (a.innerText || '').length,
      text: (a.innerText || '').replace(/\\s+/g, ' ').slice(0, 200),
      imgs: a.querySelectorAll('img').length,
      title: a.getAttribute('title') || '',
      parentTag: a.parentElement ? a.parentElement.tagName : '',
      parentCls: a.parentElement ? String(a.parentElement.className).slice(0, 80) : '',
      parentLen: a.parentElement ? (a.parentElement.innerText || '').replace(/\\s+/g, ' ').trim().length : 0
    }))
  };
}
"""


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "dom_debug2.json"
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            from urllib.parse import quote
            url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote('保温杯'.encode('gbk'))}"
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            for _ in range(3):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(600)
            data = page.evaluate(JS)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print("saved", out, data.get("count"))
        finally:
            page.close()


if __name__ == "__main__":
    main()
