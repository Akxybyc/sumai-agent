import time

from playwright.sync_api import sync_playwright

JS = """() => {
  const t = (document.body.innerText || '');
  const lines = t.split(String.fromCharCode(10)).map(s => s.trim());
  return {
    rows: document.querySelectorAll('.jx-pro-virtual-table__row').length,
    cbs: document.querySelectorAll('input[type=checkbox]').length,
    tabs: lines.filter(s => /^(全部|未认领|已认领|采集失败)/.test(s)).slice(0, 5),
    btns: [...document.querySelectorAll('button')].filter(e => e.offsetParent)
            .map(e => e.innerText.trim()).filter(Boolean).slice(0, 14),
  };
}"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    cands = [x for c in b.contexts for x in c.pages if "common_collect_box/items" in x.url]
    if cands:
        pg = cands[0]
    else:
        pg = b.contexts[0].new_page()
        pg.goto("https://erp.91miaoshou.com/common_collect_box/items",
                wait_until="domcontentloaded", timeout=45000)
    pg.bring_to_front()
    pg.wait_for_timeout(4000)
    # 先点「搜索」触发列表加载
    pg.evaluate("""() => {
      const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent)
                  .find(e => (e.innerText || '').trim() === '搜索');
      if (b) b.click();
    }""")
    pg.wait_for_timeout(4000)
    print(pg.evaluate(JS))

    # 勾选全部
    r = pg.evaluate("""() => {
      const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent)
                  .find(e => (e.innerText || '').trim() === '全选');
      if (b) { b.click(); return 'clicked 全选'; }
      return 'no 全选';
    }""")
    print(r)
    pg.wait_for_timeout(1500)

    # 点 认领到
    r2 = pg.evaluate("""() => {
      const b = [...document.querySelectorAll('button')].filter(e => e.offsetParent)
                  .find(e => /^认领到/.test((e.innerText || '').trim()));
      if (b) { b.click(); return 'clicked 认领到'; }
      return 'no 认领到';
    }""")
    print(r2)
    pg.wait_for_timeout(2000)

    items = pg.evaluate("""() => {
      const sels = ['.el-dropdown-menu', '.el-popover', '.el-popper', '[role=menu]'];
      const out = [];
      for (const s of sels) {
        for (const el of document.querySelectorAll(s)) {
          if (!el.offsetParent) continue;
          const r = el.getBoundingClientRect();
          if (r.width < 40 || r.height < 20) continue;
          const txt = (el.innerText || '').split(String.fromCharCode(10)).map(x => x.trim()).filter(Boolean);
          if (txt.length && txt.length < 12) out.push(txt.join(' | '));
        }
      }
      return out.slice(0, 8);
    }""")
    print("认领菜单:", items)
