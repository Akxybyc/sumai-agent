import json
import time

from playwright.sync_api import sync_playwright

JS = """
() => {
  const rows = Array.from(document.querySelectorAll('tr'))
    .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim())
    .filter(t => t && t.length > 4).slice(0, 12);
  const t = (document.body.innerText || '').replace(/\\s+/g, ' ');
  const marks = ['采集成功', '采集失败', '采集中', '待采集', '排队', '失败原因', '插件'];
  return {
    rows,
    hits: marks.filter(k => t.includes(k)),
    tail: t.slice(-500)
  };
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "dianxiaobao" in x.url)
    pg.bring_to_front()
    for i in range(3):
        time.sleep(8)
        data = pg.evaluate(JS)
        print(f"--- {i} ---")
        print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])
