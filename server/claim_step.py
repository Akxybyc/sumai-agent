"""手动走一遍认领，逐步截图 + 打印状态，定位卡在哪。"""
import json
import time

from playwright.sync_api import sync_playwright

URL = "https://erp.91miaoshou.com/common_collect_box/items"
OUT = "D:/WorkBuddy/sumai_agent/data"


def counts(pg):
    t = pg.evaluate("() => document.body.innerText") or ""
    out = {}
    for line in t.splitlines():
        s = line.strip()
        for k in ("全部", "未认领", "已认领"):
            if s.startswith(k + " (") and s.endswith(")"):
                out[k] = s.split("(")[1].rstrip(")")
    return out


with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pg = b.contexts[0].new_page()
    pg.goto(URL, wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(5000)
    pg.bring_to_front()

    pg.evaluate("""() => { const b=[...document.querySelectorAll('button')].filter(e=>e.offsetParent)
        .find(e=>(e.innerText||'').trim()==='搜索'); if(b) b.click(); }""")
    pg.wait_for_timeout(4000)
    print("1 初始:", counts(pg))

    pg.evaluate("""() => { const els=[...document.querySelectorAll('*')].filter(e=>e.offsetParent &&
        /^未认领\\s*\\(/.test((e.innerText||'').trim()));
        if(els.length) els[els.length-1].click(); }""")
    pg.wait_for_timeout(3000)
    rows = pg.evaluate("() => document.querySelectorAll('.jx-pro-virtual-table__row').length")
    print("2 未认领行数:", rows)
    pg.screenshot(path=f"{OUT}/claim_1_tab.png")

    pg.evaluate("""() => { const b=[...document.querySelectorAll('button')].filter(e=>e.offsetParent)
        .find(e=>(e.innerText||'').trim()==='全选'); if(b) b.click(); }""")
    pg.wait_for_timeout(1200)

    pg.evaluate("""() => { const b=[...document.querySelectorAll('button')].filter(e=>e.offsetParent)
        .find(e=>/^认领到/.test((e.innerText||'').trim())); if(b) b.click(); }""")
    pg.wait_for_timeout(2000)
    pg.screenshot(path=f"{OUT}/claim_2_menu.png")

    menus = pg.evaluate("""() => {
      const out=[];
      for (const el of document.querySelectorAll('.el-dropdown-menu, .el-popper, .el-popover, [role=menu]')) {
        if (!el.offsetParent) continue;
        const r = el.getBoundingClientRect();
        if (r.width < 60 || r.height < 20) continue;
        out.push({ txt: (el.innerText||'').split(String.fromCharCode(10)).map(s=>s.trim()).filter(Boolean).slice(0,10), x: Math.round(r.x), y: Math.round(r.y) });
      }
      return out.slice(0, 6);
    }""")
    print("3 菜单:", json.dumps(menus, ensure_ascii=False)[:400])

    # 只在下拉面板里点（排除左侧菜单，x 必须 > 300）
    ok = pg.evaluate("""() => {
      const hosts=[...document.querySelectorAll('.el-dropdown-menu, .el-popper, .el-popover, [role=menu], [class*=dropdown]')]
        .filter(e=>{ const r=e.getBoundingClientRect(); return e.offsetParent && r.width>80 && r.x>250; });
      for (const h of hosts) {
        const c=[...h.querySelectorAll('li,div,span,a')].filter(e=>e.offsetParent &&
          (e.innerText||'').trim()==='速卖通全托管');
        if (c.length) { c[0].click(); return 'dropdown@'+Math.round(h.getBoundingClientRect().x); }
      }
      return false;
    }""")
    print("4 点速卖通全托管:", ok)
    pg.wait_for_timeout(5000)
    pg.screenshot(path=f"{OUT}/claim_3_after.png")

    body = pg.evaluate("() => document.body.innerText") or ""
    lines = [x.strip() for x in body.splitlines() if x.strip()]
    hits = [x for x in lines if any(k in x for k in ("认领", "店铺", "站点", "确定", "取消", "成功", "失败", "请选择"))]
    print("5 页面提示:", hits[:10])

    pg.wait_for_timeout(3000)
    print("6 之后:", counts(pg))
    print("URL:", pg.url[-50:])
