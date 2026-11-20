"""ERP 执行层适配器。

当前接入：店小宝（1688 跨境分销 → 采集认领 → 批量发布）。
设计目标：上层只调 push_links(links)，换 ERP 只需新增一个适配器。
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data"
DATA.mkdir(exist_ok=True)


def _connect(p, port: int):
    return p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")


def _find_page(ctx, host: str):
    return next((x for x in ctx.pages if host in x.url), None)


class DianxiaobaoAdapter:
    name = "dianxiaobao"
    label = "店小宝"
    home = "https://erp.dianxiaobao.net/"
    collect_url = "https://erp.dianxiaobao.net/goods/common/copy"

    # --- 打开并识别登录态 ---
    def open_home(self, port: int = 9222) -> dict:
        with sync_playwright() as p:
            try:
                browser = _connect(p, port)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "message": f"未连接浏览器（{type(e).__name__}）"}
            ctx = browser.contexts[0]
            page = _find_page(ctx, "dianxiaobao.net") or ctx.new_page()
            page.set_viewport_size({"width": 1440, "height": 950})
            keep_open = False
            try:
                if "dianxiaobao.net" not in page.url:
                    page.goto(self.home, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(5000)
                body = page.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ')")
                need_login = ("登录" in body[:200] and "退出" not in body) or "login" in page.url.lower()
                keep_open = True  # 后续 push 要复用这个页面
                page.bring_to_front()
                page.screenshot(path=str(DATA / "erp_home.png"))
                links = page.evaluate("""
                () => Array.from(document.querySelectorAll('a')).map(a => ({
                  t: (a.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 20),
                  h: a.href
                })).filter(x => x.t && /采集|分销|商品|订单|1688|发布/.test(x.t)).slice(0, 40)
                """)
                (DATA / "erp_nav.json").write_text(
                    json.dumps({"url": page.url, "links": links}, ensure_ascii=False, indent=2), encoding="utf-8")
                return {
                    "ok": True, "need_login": need_login, "url": page.url, "title": page.title(),
                    "links": links[:12],
                    "message": "请在该窗口登录店小宝" if need_login else "已进入店小宝后台",
                }
            finally:
                if not keep_open:
                    page.close()

    # --- 推送 1688 链接到采集箱 ---
    def push_links(self, links: list[str], port: int = 9222, dry_run: bool = True) -> dict:
        links = [x for x in links if x]
        if not links:
            return {"ok": False, "message": "没有可推送的 1688 链接"}
        with sync_playwright() as p:
            try:
                browser = _connect(p, port)
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "message": f"未连接浏览器（{type(e).__name__}）"}
            ctx = browser.contexts[0]
            page = _find_page(ctx, "dianxiaobao.net")
            if page is None:
                return {"ok": False, "message": "请先打开并登录店小宝（/api/erp/open）"}
            page.bring_to_front()
            steps = []
            try:
                # 直达「采集复制」页，比点菜单稳
                if self.collect_url not in page.url:
                    page.goto(self.collect_url, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(4000)
                    steps.append("打开采集复制页")

                # 菜单兜底：若没在采集页，再试菜单入口
                if "goods/common/copy" not in page.url:
                    for text in ("1688跨境分销", "跨境分销", "采集认领", "链接采集"):
                        try:
                            loc = page.get_by_text(text, exact=False).first
                            if loc.count() > 0 and loc.is_visible():
                                loc.click(timeout=4000)
                                page.wait_for_timeout(2000)
                                steps.append(f"点击 {text}")
                                break
                        except Exception:
                            continue

                # 关掉可能挡住的提示弹窗（插件提示等）
                for close_text in ("取消", "关闭"):
                    try:
                        btn = page.get_by_text(close_text, exact=True).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click(timeout=2500)
                            steps.append(f"关闭弹窗({close_text})")
                            page.wait_for_timeout(800)
                            break
                    except Exception:
                        continue

                # 找粘贴链接的输入区（可能有隐藏 textarea，需挑可见的那个）
                filled = False
                tas = page.locator("textarea")
                probe = []
                for i in range(tas.count()):
                    try:
                        box = tas.nth(i)
                        vis = box.is_visible()
                        ph = (box.get_attribute("placeholder") or "")[:12]
                        probe.append(f"#{i} vis={vis} ph={ph}")
                        if not vis:
                            continue
                        box.click(timeout=3000)
                        box.fill("\n".join(links))
                        filled = True
                        steps.append(f"粘贴 {len(links)} 条链接（textarea#{i}）")
                        break
                    except Exception as e:  # noqa: BLE001
                        probe.append(f"#{i} err={type(e).__name__}")
                        continue
                if not filled and probe:
                    steps.append("探测：" + " / ".join(probe))

                if not filled:
                    page.screenshot(path=str(DATA / "erp_push_fail.png"))
                    return {"ok": False, "steps": steps,
                            "message": "没找到链接输入框，可能需要先登录或进入采集认领页"}

                if not dry_run:
                    # 先勾「商品信息授权使用承诺书」
                    try:
                        cb = page.locator("input[type='checkbox']").first
                        if cb.count() > 0 and not cb.is_checked():
                            cb.check(force=True, timeout=3000)
                            steps.append("勾选授权承诺书")
                    except Exception:
                        try:
                            page.get_by_text("商品信息授权使用承诺书", exact=False).first.click(timeout=2500)
                            steps.append("勾选授权承诺书(文本)")
                        except Exception:
                            pass

                    # 承诺书弹窗要点「确定签署」
                    for sign in ("确定签署", "确认签署", "同意"):
                        try:
                            btn = page.get_by_text(sign, exact=True).first
                            if btn.count() > 0 and btn.is_visible():
                                btn.click(timeout=3000)
                                steps.append(f"点击 {sign}")
                                page.wait_for_timeout(1500)
                                break
                        except Exception:
                            continue

                    for text in ("开始采集", "采集", "采集并认领"):
                        try:
                            btn = page.get_by_text(text, exact=True).first
                            if btn.count() > 0 and btn.is_visible():
                                btn.click(timeout=4000)
                                steps.append(f"点击 {text}")
                                page.wait_for_timeout(3000)
                                break
                        except Exception:
                            continue

                    page.wait_for_timeout(8000)

                page.screenshot(path=str(DATA / "erp_pushed.png"))
                state = page.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 300)")
                return {"ok": True, "steps": steps, "count": len(links), "dry_run": dry_run, "state": state}
            except Exception as e:  # noqa: BLE001
                page.screenshot(path=str(DATA / "erp_push_error.png"))
                return {"ok": False, "steps": steps, "message": f"{type(e).__name__}: {e}"}


ADAPTERS = {DianxiaobaoAdapter.name: DianxiaobaoAdapter()}


def get_adapter(name: str = "dianxiaobao"):
    return ADAPTERS.get(name)
