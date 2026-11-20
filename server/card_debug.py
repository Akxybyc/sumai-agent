import json
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """
() => {
  const cards = Array.from(document.querySelectorAll('.pcard')).slice(0, 1);
  return cards.map(c => {
    const img = c.querySelector('.pimg');
    const body = c.querySelector('.pbody');
    const t = c.querySelector('.ptitle');
    const tr = t ? t.getBoundingClientRect() : null;
    const topEl = tr ? document.elementFromPoint(tr.x + 6, tr.y + 6) : null;
    const cs = t ? getComputedStyle(t) : null;
    return {
      html: c.outerHTML.slice(0, 1200),
      imgH: img ? getComputedStyle(img).height : null,
      cardH: getComputedStyle(c).height,
      bodyH: body ? getComputedStyle(body).height : null,
      bodyText: body ? body.innerText.slice(0, 80) : null,
      bodyColor: body ? getComputedStyle(body.querySelector('.ptitle') || body).color : null,
      cardRect: c.getBoundingClientRect().toJSON(),
      bodyRect: body ? body.getBoundingClientRect().toJSON() : null,
      imgRect: img ? img.getBoundingClientRect().toJSON() : null,
      titleRect: tr ? tr.toJSON() : null,
      titleStyle: cs ? {size: cs.fontSize, color: cs.color, display: cs.display, opacity: cs.opacity, visibility: cs.visibility, zIndex: cs.zIndex} : null,
      topElement: topEl ? (topEl.className || topEl.tagName) : null,
      topInfo: topEl && topEl.tagName === "IMG" ? {
        src: (topEl.src || "").slice(-60),
        rect: topEl.getBoundingClientRect().toJSON(),
        parent: topEl.parentElement ? topEl.parentElement.className : "",
        pos: getComputedStyle(topEl).position,
        z: getComputedStyle(topEl).zIndex
      } : null
    };
  });
}
"""

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = browser.contexts[0]
    page = ctx.new_page()
    page.goto("http://127.0.0.1:8000/", wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    data = page.evaluate(JS)
    Path("D:/WorkBuddy/sumai_agent/data/card_debug.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    page.screenshot(path="D:/WorkBuddy/sumai_agent/data/page_shot.png", full_page=False)
    page.close()
print("ok")
