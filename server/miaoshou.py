"""妙手 ERP 适配器（RPA 采集 → 速卖通全托管采集箱）。

已验证事实（2026-11-08）：
- 链接采集页 https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy
- 输入框支持 `链接$$自定义英文标题`，多行分隔
- 采集后可自动认领到「速卖通全托管采集箱」（用户在妙手配置了自动认领 2 个平台）
- 页面上「1688 未授权」提示不可信，实际可采集
- 采集箱列表行含「货源：991730585225」与认领时间，可用于结果校验
"""

from __future__ import annotations

import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

DATA = Path(__file__).resolve().parent.parent / "data"

ERP_HOME = "https://erp.91miaoshou.com/"
LINK_COPY = "https://erp.91miaoshou.com/common_collect_box/index?fetchType=linkCopy"
BOX_SIDEBAR_TEXT = "速卖通全托管采集箱"
ROW_SEL = ".jx-pro-virtual-table__row"   # 虚拟表格行（div 结构）


def _page(browser, prefer_substr: str = "91miaoshou.com"):
    pages = [p for c in browser.contexts for p in c.pages]
    hit = [p for p in pages if prefer_substr in p.url and "agent.html" not in p.url]
    return hit[0] if hit else None


class MiaoshouAdapter:
    name = "miaoshou"
    label = "妙手ERP"

    # ---------- 打开后台 ----------
    def open_home(self, port: int = 9222) -> dict:
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            pg = _page(b)
            if pg is None:
                pg = b.contexts[0].new_page()
                pg.goto(ERP_HOME, wait_until="domcontentloaded", timeout=60000)
            else:
                pg.bring_to_front()
            pg.wait_for_timeout(2500)
            url = pg.url
            need_login = "/welcome" not in url and "login" in url.lower()
            return {"ok": True, "url": url, "need_login": need_login, "title": pg.title()}

    # ---------- 采集箱页 ----------
    def _open_box(self, pg) -> bool:
        """点侧边栏进入「速卖通全托管」采集箱，兼容不同文案。"""
        labels = [BOX_SIDEBAR_TEXT, "速卖通全托管", "速卖通全托管采集箱"]
        start_url = pg.url
        for label in labels:
            for _ in range(2):
                clicked = pg.evaluate(
                    """(label) => {
                  const els = Array.from(document.querySelectorAll('a, span, li, div'))
                    .filter(e => e.offsetParent !== null && (e.innerText || '').trim() === label)
                    .sort((a, b) => a.innerText.length - b.innerText.length);
                  if (els.length) { els[0].click(); return true; }
                  return false;
                }""",
                    label,
                )
                if clicked:
                    pg.wait_for_timeout(4000)
                    if pg.url != start_url or "collect_box" in pg.url:
                        return True
                pg.wait_for_timeout(800)
        return False

    def box_rows(self, port: int = 9222, limit: int = 30) -> dict:
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            pg = _page(b)
            if pg is None:
                return {"ok": False, "message": "未连接妙手页面"}
            ok = self._open_box(pg)
            rows = pg.evaluate(
                """(sel) => Array.from(document.querySelectorAll(sel))
              .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean)""",
                ROW_SEL,
            )
            return {"ok": ok, "url": pg.url, "rows": rows[:limit]}

    # ---------- 预填（人工点提交） ----------
    def prepare(self, items: list[dict], port: int = 9222) -> dict:
        """把链接+标题填进妙手采集框，停住等人工点『采集并自动认领』。"""
        links = [f"{i['url']}$${i['title'][:110]}" for i in items if i.get("url")]
        if not links:
            return {"ok": False, "message": "没有可填的链接"}
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            pg = _page(b)
            if pg is None:
                return {"ok": False, "message": "未连接浏览器"}
            try:
                pg.goto(LINK_COPY, wait_until="domcontentloaded", timeout=60000)
                pg.wait_for_timeout(5000)
                pg.evaluate(
                    """() => {
                  const b = Array.from(document.querySelectorAll('button, span, div'))
                    .filter(e => e.offsetParent && (e.innerText || '').trim() === '我知道了')[0];
                  if (b) b.click();
                }"""
                )
                pg.wait_for_timeout(500)
                pg.evaluate(
                    """() => {
                  const ta = document.querySelector('textarea');
                  if (!ta) return;
                  ta.focus(); ta.value = '';
                  ta.dispatchEvent(new Event('input', {bubbles: true}));
                  ta.dispatchEvent(new Event('change', {bubbles: true}));
                }"""
                )
                pg.wait_for_timeout(300)
                pg.evaluate(
                    """(txt) => {
                  const ta = document.querySelector('textarea');
                  ta.focus();
                  document.execCommand('insertText', false, txt);
                }""",
                    "\n".join(links),
                )
                pg.wait_for_timeout(1200)
                state = pg.evaluate(
                    """() => {
                  const ta = document.querySelector('textarea');
                  const b = Array.from(document.querySelectorAll('button'))
                    .find(e => (e.innerText || '').trim() === '采集并自动认领');
                  return {taLen: ta ? ta.value.length : -1,
                          btnFound: !!b, btnDisabled: b ? b.disabled : null};
                }"""
                )
                pg.screenshot(path=str(DATA / "ms_prepared.png"))
                ok = state["taLen"] > 0 and state["btnDisabled"] is False
                return {
                    "ok": ok,
                    "count": len(links),
                    "state": state,
                    "url": pg.url,
                    "message": (f"已填入 {len(links)} 条，去妙手点『采集并自动认领』"
                                if ok else f"填入异常：文本 {state['taLen']} 字，按钮禁用 {state['btnDisabled']}"),
                }
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "message": f"{type(e).__name__}: {e}"}

    # ---------- 采集 ----------
    def collect(self, items: list[dict], port: int = 9222, dry_run: bool = True,
                wait_sec: int = 35) -> dict:
        """items: [{url, title, source_id}]"""
        links = [f"{i['url']}$${i['title'][:110]}" for i in items if i.get("url")]
        expected = {str(i.get("source_id") or "") for i in items}
        expected.discard("")
        if not links:
            return {"ok": False, "message": "没有可采集的链接"}

        steps: list[str] = []
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            pg = _page(b)
            if pg is None:
                return {"ok": False, "message": "未连接浏览器（请先启动调试 Chrome 并登录妙手）"}
            try:
                if "common_collect_box" not in pg.url:
                    pg.goto(LINK_COPY, wait_until="domcontentloaded", timeout=60000)
                    pg.wait_for_timeout(4000)
                    steps.append("打开发布采集页")

                # 关掉可能的浮层
                pg.evaluate(
                    """() => {
                  const b = Array.from(document.querySelectorAll('button, a, div, span'))
                    .filter(e => e.offsetParent && (e.innerText || '').trim() === '我知道了')[0];
                  if (b) b.click();
                }"""
                )

                # 这个输入框 fill('')/全选删除都清不掉，只能用 JS 清空并 insertText 写入
                pg.evaluate(
                    """() => {
                  const ta = document.querySelector('textarea');
                  if (!ta) return;
                  ta.focus();
                  ta.value = '';
                  ta.dispatchEvent(new Event('input', {bubbles: true}));
                  ta.dispatchEvent(new Event('change', {bubbles: true}));
                }"""
                )
                pg.wait_for_timeout(400)
                pg.evaluate(
                    """(txt) => {
                  const ta = document.querySelector('textarea');
                  ta.focus();
                  document.execCommand('insertText', false, txt);
                }""",
                    "\n".join(links),
                )
                pg.wait_for_timeout(900)
                steps.append(f"粘贴 {len(links)} 条链接（含英文标题）")
                pg.wait_for_timeout(1200)
                pg.locator("textarea").first.blur()
                pg.wait_for_timeout(600)

                if dry_run:
                    pg.screenshot(path=str(DATA / "ms_collect_dryrun.png"))
                    return {"ok": True, "dry_run": True, "steps": steps,
                            "count": len(links), "message": "已填入链接（dry_run 未提交）"}

                # 优先点「采集并自动认领」，其次「采集」
                # 按钮禁用时说明输入校验没通过，直接报告内容
                btn_state = pg.evaluate(
                    """() => {
                  const b = Array.from(document.querySelectorAll('button'))
                    .find(e => (e.innerText || '').trim() === '采集并自动认领');
                  const ta = document.querySelector('textarea');
                  return {found: !!b, disabled: b ? b.disabled : null,
                          taLen: ta ? (ta.value || '').length : -1,
                          taVal: ta ? (ta.value || '').slice(0, 80) : ''};
                }"""
                )
                if btn_state.get("disabled"):
                    return {"ok": False, "steps": steps,
                            "message": f"采集按钮被禁用（输入校验未通过）：{btn_state.get('taVal')}"}

                clicked = None
                click_err = ""
                # 该按钮对 JS click 不响应，必须用真实鼠标坐标点击
                for text in ("采集并自动认领", "采集并自动发布", "开始采集"):
                    box = pg.evaluate(
                        """(t) => {
                      const b = Array.from(document.querySelectorAll('button'))
                        .find(e => e.offsetParent && (e.innerText || '').trim() === t);
                      if (!b) return null;
                      const r = b.getBoundingClientRect();
                      return {x: r.x + r.width / 2, y: r.y + r.height / 2, disabled: b.disabled};
                    }""",
                        text,
                    )
                    if not box:
                        continue
                    if box.get("disabled"):
                        clicked = None
                        click_err = f"{text} 处于禁用状态"
                        continue
                    try:
                        pg.mouse.click(box["x"], box["y"])
                        clicked = text
                        break
                    except Exception as ce:  # noqa: BLE001
                        click_err = f"{type(ce).__name__}: {str(ce)[:100]}"
                if clicked:
                    steps.append(f"点击「{clicked}」" + (f"（页面报错已忽略：{click_err}）" if click_err else ""))
                else:
                    pg.locator("textarea").first.press("Control+Enter")
                    steps.append("按钮未找到，已按 Ctrl+Enter 提交")

                # 抓现场：提示框/吐司/输入框是否被清空
                pg.wait_for_timeout(1500)
                diag = pg.evaluate(
                    """() => {
                  const vis = e => e.offsetParent !== null;
                  const dlg = Array.from(document.querySelectorAll('[class*="dialog"],[class*="modal"]'))
                    .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                    .filter(t => t).slice(0, 2);
                  const toast = Array.from(document.querySelectorAll('[class*="message"],[class*="toast"]'))
                    .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                    .filter(t => t).slice(0, 2);
                  const ta = document.querySelector('textarea');
                  return {dlg, toast, taLen: ta ? (ta.value || '').length : -1};
                }"""
                )
                steps.append(f"提交后反馈：{diag.get('dlg') or diag.get('toast') or '无弹窗'}；输入框剩余 {diag.get('taLen')} 字")

                # 关掉“已提交采集任务”提示框，否则挡住后续操作
                pg.wait_for_timeout(300)
                pg.evaluate("""
                () => {
                  const b = Array.from(document.querySelectorAll('button, a, div, span'))
                    .filter(e => e.offsetParent && (e.innerText || '').trim() === '我知道了')[0];
                  if (b) b.click();
                }
                """)

                pg.wait_for_timeout(wait_sec * 1000)

                # 校验：进采集箱看是否出现
                try:
                    box_ok = self._open_box(pg)
                except Exception as be:  # noqa: BLE001
                    box_ok = False
                    steps.append(f"进入采集箱校验时出错（已忽略）：{type(be).__name__}")
                rows = pg.evaluate(
                    """(sel) => Array.from(document.querySelectorAll(sel))
                    .map(tr => (tr.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean)""",
                    ROW_SEL,
                )
                found = []
                for r in rows:
                    m = re.search(r"货源[：:]\s*[（(]?\s*(\d{6,})", r)
                    if m and (not expected or m.group(1) in expected):
                        found.append(m.group(1))
                steps.append(f"采集箱校验：命中 {len(found)} 条")
                pg.screenshot(path=str(DATA / "ms_collect_done.png"))
                return {
                    "ok": len(found) > 0 or not expected,
                    "count": len(found),
                    "found": found,
                    "box_url": pg.url,
                    "rows": rows[:8],
                    "steps": steps,
                    "message": "采集成功" if found else "未在采集箱找到对应商品，请人工确认",
                }
            except Exception as e:  # noqa: BLE001
                try:
                    pg.screenshot(path=str(DATA / "ms_collect_error.png"))
                except Exception:
                    pass
                return {"ok": False, "steps": steps, "message": f"{type(e).__name__}: {e}"}


    # ---------- 勾选待发布（不点发布） ----------
    def select_for_publish(self, source_ids: list[str], port: int = 9222) -> dict:
        """在速卖通全托管采集箱里勾选指定货源商品，并列出可用的发布按钮（不点击）。"""
        ids = {str(i) for i in source_ids if i}
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            pg = _page(b)
            if pg is None:
                return {"ok": False, "message": "未连接浏览器"}
            try:
                if not self._open_box(pg):
                    return {"ok": False, "message": "进不去速卖通全托管采集箱"}
                pg.wait_for_timeout(2500)
                hit = pg.evaluate(
                    """(ids) => {
                  const out = [];
                  document.querySelectorAll('.jx-pro-virtual-table__row').forEach((tr) => {
                    const t = (tr.innerText || '').replace(/\s+/g, ' ');
                    const m = t.match(/货源[：:]\s*[（(]?\s*(\d{6,})/);
                    if (m && ids.includes(m[1])) {
                      const cb = tr.querySelector('input[type=checkbox]');
                      if (cb && !cb.checked) cb.click();
                      out.push(m[1]);
                    }
                  });
                  return out;
                }""",
                    list(ids),
                )
                pg.wait_for_timeout(800)
                btns = pg.evaluate(
                    """() => Array.from(document.querySelectorAll('button'))
                  .filter(e => e.offsetParent).map(e => (e.innerText || '').trim())
                  .filter(t => t).slice(0, 20)"""
                )
                pg.screenshot(path=str(DATA / "ms_box_selected.png"))
                return {"ok": bool(hit), "selected": hit, "buttons": btns,
                        "url": pg.url,
                        "message": f"已勾选 {len(hit)} 条，按钮：{' / '.join(btns[:8])}"}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "message": f"{type(e).__name__}: {e}"}

    # ---------- 发布 ----------
    def publish(self, source_ids: list[str], port: int = 9222, dry_run: bool = True,
                wait_sec: int = 25) -> dict:
        """在速卖通全托管采集箱里对指定货源商品执行发布（dry_run 只定位并停住）。"""
        ids = {str(i) for i in source_ids if i}
        steps: list[str] = []
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            pg = _page(b)
            if pg is None:
                return {"ok": False, "message": "未连接浏览器"}
            try:
                if not self._open_box(pg):
                    return {"ok": False, "message": "进不去速卖通全托管采集箱（请确认已登录妙手）"}
                steps.append("进入速卖通全托管采集箱")
                pg.wait_for_timeout(2500)

                hit = pg.evaluate(
                    """(ids) => {
                  const rows = Array.from(document.querySelectorAll('.jx-pro-virtual-table__row'));
                  const out = [];
                  rows.forEach((tr) => {
                    const t = (tr.innerText || '').replace(/\\s+/g, ' ');
                    const m = t.match(/货源[：:]\\s*[（(]?\\s*(\\d{6,})/);
                    if (m && ids.includes(m[1])) {
                      const cb = tr.querySelector('input[type=checkbox]');
                      if (cb && !cb.checked) cb.click();
                      out.push(m[1]);
                    }
                  });
                  return out;
                }""",
                    list(ids),
                )
                steps.append(f"勾选命中 {len(hit)} 条：{hit}")
                pg.wait_for_timeout(800)
                pg.screenshot(path=str(DATA / "ms_publish_selected.png"))

                if not hit:
                    return {"ok": False, "steps": steps,
                            "message": "采集箱里没有这些货源商品，先推送采集"}
                if dry_run:
                    return {"ok": True, "dry_run": True, "steps": steps, "found": hit,
                            "message": "已勾选，未发布"}

                clicked = None
                for text in ("批量发布", "发布"):
                    loc = pg.get_by_text(text, exact=True)
                    for i in range(loc.count()):
                        el = loc.nth(i)
                        try:
                            if el.is_visible():
                                el.click(timeout=5000, force=True)
                                clicked = text
                                break
                        except Exception:
                            continue
                    if clicked:
                        break
                steps.append(f"点击「{clicked}」" if clicked else "未找到发布按钮")
                pg.wait_for_timeout(wait_sec * 1000)

                # 抓取可能的阻断弹窗（例如类目未设置）
                modal = pg.evaluate(
                    """() => {
                  const vis = e => e.offsetParent !== null;
                  const m = Array.from(document.querySelectorAll('[class*="dialog"],[class*="modal"]'))
                    .filter(vis).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim()).filter(Boolean);
                  return m.slice(0, 3);
                }"""
                )
                toast = pg.evaluate(
                    """() => Array.from(document.querySelectorAll('[class*="message"],[class*="toast"]'))
                  .filter(e => e.offsetParent).map(e => (e.innerText || '').replace(/\\s+/g, ' ').trim())
                  .filter(Boolean).slice(0, 3)"""
                )
                pg.screenshot(path=str(DATA / "ms_publish_done.png"))
                blocked_text = " ".join(modal) if modal else ""
                return {
                    "ok": not blocked_text,
                    "found": hit,
                    "clicked": clicked,
                    "modal": modal,
                    "toast": toast,
                    "steps": steps,
                    "message": ("需要先补全：" + blocked_text[:120]) if blocked_text else "已提交发布，请在发布记录核对",
                }
            except Exception as e:  # noqa: BLE001
                try:
                    pg.screenshot(path=str(DATA / "ms_publish_error.png"))
                except Exception:
                    pass
                return {"ok": False, "steps": steps, "message": f"{type(e).__name__}: {e}"}


ADAPTERS = {MiaoshouAdapter.name: MiaoshouAdapter()}


def get_adapter(name: str = "miaoshou"):
    return ADAPTERS.get(name)
