from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    html = pg.evaluate(
        """() => {
      const ta = document.querySelector('textarea');
      let box = ta;
      for (let i = 0; i < 3 && box.parentElement; i++) box = box.parentElement;
      const sibs = Array.from(box.parentElement.children).map(e => e.outerHTML.slice(0, 600));
      return sibs.join('\\n---SIB---\\n').slice(0, 3000);
    }"""
    )
    print(html)
