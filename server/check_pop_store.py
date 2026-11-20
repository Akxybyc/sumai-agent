import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "goods-wait" in x.url)
    pg.bring_to_front()
    # 打开店铺下拉
    pg.evaluate("""
    () => {
      const sels = Array.from(document.querySelectorAll('.ivu-select')).filter(e => e.offsetParent);
      const storeSel = sels.find(e => (e.innerText || '').includes('Shop1105202845'));
      if (storeSel) {
        const head = storeSel.querySelector('.ivu-select-selection');
        if (head) head.click();
      }
    }
    """)
    pg.wait_for_timeout(1500)
    # 选 cn1107939087gdhae
    r = pg.evaluate("""
    () => {
      const opt = Array.from(document.querySelectorAll('.ivu-select-dropdown li, .ivu-select-item'))
        .filter(e => e.offsetParent)
        .find(e => (e.innerText || '').includes('cn1107939087gdhae'));
      if (opt) { opt.click(); return (opt.innerText || '').trim().slice(0, 40); }
      return 'not-found';
    }
    """)
    print("switch to:", r)
    pg.wait_for_timeout(5000)
    data = pg.evaluate("""
    () => ({
      url: location.href,
      store: (document.querySelector('.ivu-select-selected-value') || {}).innerText || '',
      rows: Array.from(document.querySelectorAll('tbody tr'))
        .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 90)).slice(0, 6)
    })
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])
