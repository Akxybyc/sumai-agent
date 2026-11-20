"""调试：导出 1688 详情页结构，用于确定 SKU / 图片 / 重量提取规则。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """
() => {
  const txt = (el) => el ? (el.innerText || '').replace(/\\s+/g, ' ').trim() : '';
  const cls = (el) => el ? String(el.className || '').slice(0, 80) : '';
  const imgs = Array.from(document.querySelectorAll('img')).map(i => i.src)
    .filter(s => s && (s.includes('cbu01') || s.includes('alicdn')));
  const skuNodes = Array.from(document.querySelectorAll('[class*="sku"], [class*="Sku"], [class*="prop"]'))
    .slice(0, 40).map(e => ({tag: e.tagName, cls: cls(e), text: txt(e).slice(0, 120)}));
  const priceNodes = Array.from(document.querySelectorAll('[class*="price"], [class*="Price"]'))
    .slice(0, 20).map(e => ({cls: cls(e), text: txt(e).slice(0, 80)}));
  return {
    url: location.href,
    title: document.title,
    h1: txt(document.querySelector('h1')),
    body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 3500),
    imgCount: imgs.length,
    images: Array.from(new Set(imgs)).slice(0, 12),
    skuNodes,
    priceNodes,
    h1Count: document.querySelectorAll('h1').length
  };
}
"""


def main(offer_url: str) -> None:
    out = Path(__file__).resolve().parent.parent / "data" / "detail_debug.json"
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
        ctx = browser.contexts[0]
        page = ctx.new_page()
        try:
            page.goto(offer_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500)
            for _ in range(3):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(600)
            data = page.evaluate(JS)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            page.screenshot(path=str(out.with_suffix(".png")))
            print("saved", out, "imgs", data.get("imgCount"))
        finally:
            page.close()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "http://detail.1688.com/offer/991730585225.html")
