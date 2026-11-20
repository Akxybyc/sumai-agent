import json
from pathlib import Path

from playwright.sync_api import sync_playwright

JS = """
() => {
  const items = [];
  document.querySelectorAll('a, [role="menuitem"], li, div[class*="menu"]').forEach(el => {
    const t = (el.innerText || '').replace(/\\s+/g, ' ').trim();
    if (!t || t.length > 24) return;
    if (!/发布|商品|上新|提报|供货|管理/.test(t)) return;
    items.push({text: t, href: el.getAttribute('href') || '', tag: el.tagName});
  });
  return {
    url: location.href,
    title: document.title,
    body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 600),
    items: items.slice(0, 80)
  };
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.set_viewport_size({"width": 1440, "height": 950})
    pg.goto("https://csp.aliexpress.com/m_apps/newhome/choice?channelId=2590500",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    pg.bring_to_front()
    data = pg.evaluate(JS)
    Path("D:/WorkBuddy/sumai_agent/data/ae_links.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    pg.screenshot(path="D:/WorkBuddy/sumai_agent/data/ae_home.png")
    print("ok", data["url"])
