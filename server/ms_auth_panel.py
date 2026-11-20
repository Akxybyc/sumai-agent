from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    html = pg.evaluate(
        """() => {
      const els = Array.from(document.querySelectorAll('*'))
        .filter(e => e.offsetParent && /1688\\s*未授权/.test(e.innerText || ''))
        .sort((a, b) => a.innerText.length - b.innerText.length);
      if (!els.length) return 'not-found';
      let box = els[0];
      for (let i = 0; i < 3 && box.parentElement; i++) box = box.parentElement;
      return box.outerHTML.slice(0, 3500);
    }"""
    )
    print(html)
