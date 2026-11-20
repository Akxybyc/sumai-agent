import time

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc" in x.url)
    pg.bring_to_front()

    if not pg.evaluate("() => !!document.querySelector('.category-attribute-list')"):
        pg.evaluate("""() => {
          const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
          for (const r of rows) {
            const btn = Array.from(r.querySelectorAll('a, span, button, div'))
              .find(e => (e.innerText || '').trim() === '编辑');
            if (btn) { btn.click(); return true; }
          }
        }""")
        pg.wait_for_timeout(7000)
    print("editor:", pg.evaluate("() => !!document.querySelector('.category-attribute-list')"))

    # 点开「产地」下拉
    pg.evaluate("""() => {
      const it = Array.from(document.querySelectorAll('.category-attribute-item'))
        .find(e => (e.innerText || '').trim().startsWith('产地'));
      const inp = it && (it.querySelector('.el-select .el-input__inner') || it.querySelector('.el-input__inner'));
      if (inp) inp.click();
    }""")
    time.sleep(1.5)

    # 用 role 定位选项（可穿透传送弹层）
    print("option count:", pg.get_by_role("option").count())
    try:
        opt = pg.get_by_role("option", name="中国大陆(Origin)")
        print("match:", opt.count())
        if opt.count():
            opt.first.click()
            time.sleep(1)
    except Exception as e:
        print("role click err:", type(e).__name__, str(e)[:120])

    val = pg.evaluate("""() => {
      const it = Array.from(document.querySelectorAll('.category-attribute-item'))
        .find(e => (e.innerText || '').trim().startsWith('产地'));
      const tag = it && it.querySelector('.el-tag, .el-select__tags-text');
      const inp = it && it.querySelector('.el-input__inner');
      return (tag && tag.innerText.trim()) || (inp && inp.value) || '(空)';
    }""")
    print("产地 现值:", val)
