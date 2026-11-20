import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages
              if "91miaoshou" in x.url and "welcome" not in x.url and "agent" not in x.url)
    pg.bring_to_front()
    # 找所有含 采集/刊登/发布 的可点元素和链接
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const links = Array.from(document.querySelectorAll('a'))
        .filter(vis)
        .map(a => ({t: (a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 14), h: a.href}))
        .filter(x => x.t && /采集|刊登|发布|商品/.test(x.t)).slice(0, 25);
      const nodes = Array.from(document.querySelectorAll('span,li,div'))
        .filter(vis)
        .map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
        .filter(t => t && t.length <= 8 && /产品采集|链接采集|刊登|批量发布|采集箱/.test(t))
        .slice(0, 20);
      return {url: location.href, links, nodes};
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1800])
