import json
import time

from playwright.sync_api import sync_playwright

FIELDS = ["产地", "材质", "高关注化学品", "功能", "特性", "风格", "固定方式", "外形因素"]

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "aliexpress_fc" in x.url and "collect_box" in x.url)
    pg.bring_to_front()

    # 点开第一个 el-select，确认弹层选择器
    pg.evaluate(
        """() => {
      const item = Array.from(document.querySelectorAll('.el-form-item'))
        .find(e => (e.innerText || '').includes('高关注化学品'));
      const inp = item && item.querySelector('.el-select input:not([type=hidden])');
      if (inp) inp.click();
    }"""
    )
    time.sleep(1.5)
    probe = pg.evaluate(
        """() => {
      const vis = e => e.offsetParent !== null;
      const lists = Array.from(document.querySelectorAll('.el-select-dropdown, .el-select-dropdown__list'))
        .filter(vis).map(e => e.className);
      const items = Array.from(document.querySelectorAll('.el-select-dropdown__item'))
        .filter(vis).map(e => (e.innerText || '').trim()).slice(0, 15);
      return {lists, items};
    }"""
    )
    print("probe:", json.dumps(probe, ensure_ascii=False)[:600])
    pg.keyboard.press("Escape")
