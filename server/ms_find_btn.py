import json

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = next(x for c in b.contexts for x in c.pages if "common_collect_box" in x.url)
    pg.bring_to_front()
    # 关掉“我知道了”
    pg.evaluate("""
    () => {
      const btn = Array.from(document.querySelectorAll('button, a, div, span'))
        .filter(e => e.offsetParent && (e.innerText || '').trim() === '我知道了')[0];
      if (btn) btn.click();
    }
    """)
    pg.wait_for_timeout(1000)
    # 找所有含“采集”的可点元素（排除菜单项）
    data = pg.evaluate("""
    () => {
      const vis = e => e.offsetParent !== null;
      const els = Array.from(document.querySelectorAll('button, a, [class*="btn"], [class*="button"]'))
        .filter(vis)
        .map(e => ({t: (e.innerText || '').replace(/\\s+/g, ' ').trim(), cls: String(e.className).slice(0, 40)}))
        .filter(x => x.t && /采集/.test(x.t)).slice(0, 15);
      // 1688 授权状态
      const auth = (document.body.innerText || '').match(/1688[^无]{0,6}未授权|1688\\s*已授权/);
      return {collectButtons: els, auth1688: auth ? auth[0] : 'not-found'};
    }
    """)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:1200])
