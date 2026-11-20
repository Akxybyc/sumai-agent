from playwright.sync_api import sync_playwright

JS = """
() => {
  const t = (document.body.innerText || '').replace(/\\s+/g, ' ');
  const hits = ['批量', '导入', '复制', '模板', 'Excel', '下载'].filter(k => t.includes(k));
  const idx = {};
  hits.forEach(k => { idx[k] = t.indexOf(k); });
  return {
    url: location.href,
    title: document.title,
    hits,
    snippets: hits.map(k => t.slice(Math.max(0, idx[k] - 30), idx[k] + 50)),
    buttons: Array.from(document.querySelectorAll('button,a'))
      .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
      .filter(x => x && x.length < 12).slice(0, 50)
  };
}
"""

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    ctx = b.contexts[0]
    pg = ctx.new_page()
    pg.goto("https://csp.aliexpress.com/m_apps/choiceProductManage/list-manage",
            wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(6000)
    import json
    print(json.dumps(pg.evaluate(JS), ensure_ascii=False))
    pg.close()
