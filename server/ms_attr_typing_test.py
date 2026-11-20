import json
import time

from playwright.sync_api import sync_playwright

FIELDS = [("材质", "塑料"), ("功能", "防尘"), ("风格", "现代")]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc" in x.url)
    pg.bring_to_front()

    # 确保编辑抽屉打开
    if not pg.evaluate("() => !!document.querySelector('.category-attribute-list')"):
        pg.evaluate(
            """() => {
          const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
          for (const r of rows) {
            const btn = Array.from(r.querySelectorAll('a, span, button, div'))
              .find(e => (e.innerText || '').trim() === '编辑');
            if (btn) { btn.click(); return true; }
          }
        }"""
        )
        pg.wait_for_timeout(7000)
    print("editor:", pg.evaluate("() => !!document.querySelector('.category-attribute-list')"))

    for field, kw in FIELDS:
        # 聚焦该属性的 select 输入框
        ok = pg.evaluate(
            """(name) => {
          const items = Array.from(document.querySelectorAll('.category-attribute-item'));
          const it = items.find(e => (e.innerText || '').trim().startsWith(name));
          if (!it) return 'no-item';
          const inp = it.querySelector('.el-select input') || it.querySelector('.el-input__inner');
          if (!inp) return 'no-input';
          inp.focus(); inp.click();
          return 'focused';
        }""",
            field,
        )
        time.sleep(0.8)
        pg.keyboard.type(kw, delay=60)
        time.sleep(1.0)
        shown = pg.evaluate(
            """() => {
          const dds = Array.from(document.querySelectorAll('.el-select-dropdown')).filter(e => e.offsetParent);
          const dd = dds[dds.length - 1];
          return dd ? Array.from(dd.querySelectorAll('.el-select-dropdown__item'))
            .filter(e => e.offsetParent).map(e => e.innerText.trim()).slice(0, 5) : [];
        }"""
        )
        pg.keyboard.press("Enter")
        time.sleep(0.8)
        val = pg.evaluate(
            """(name) => {
          const items = Array.from(document.querySelectorAll('.category-attribute-item'));
          const it = items.find(e => (e.innerText || '').trim().startsWith(name));
          if (!it) return '';
          const tag = it.querySelector('.el-tag, .el-select__tags-text');
          const inp = it.querySelector('.el-input__inner');
          return (tag && tag.innerText.trim()) || (inp && inp.value) || '';
        }""",
            field,
        )
        print(f"{field} focus={ok} 候选={shown[:3]} 选中='{val}'")
