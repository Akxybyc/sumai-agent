"""速卖通卖家后台 RPA（全托管 · 发布商品提报）。

本轮只做「打开 → 识别登录 → 抓表单结构」，不提交任何数据。
"""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "data"
DATA.mkdir(exist_ok=True)

SELLER_URL = "https://csp.aliexpress.com/m_apps/newhome/choice?channelId=2590500"

DUMP_JS = """
() => {
  const txt = (el) => el ? (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 40) : '';
  const labelOf = (el) => {
    const wrap = el.closest('label');
    if (wrap) return txt(wrap);
    const id = el.id;
    if (id) {
      const l = document.querySelector(`label[for="${id}"]`);
      if (l) return txt(l);
    }
    const parent = el.parentElement;
    return parent ? txt(parent) : '';
  };
  const inputs = Array.from(document.querySelectorAll('input, select, textarea'))
    .filter(e => e.offsetParent !== null)
    .slice(0, 80)
    .map(e => ({
      tag: e.tagName, type: e.type || '', id: e.id || '', name: e.name || '',
      ph: e.placeholder || '', label: labelOf(e),
      required: !!(e.required || (e.getAttribute('aria-required') === 'true'))
    }));
  const buttons = Array.from(document.querySelectorAll('button, [role="button"]'))
    .filter(e => e.offsetParent !== null)
    .map(e => txt(e)).filter(t => t).slice(0, 40);
  return {
    url: location.href,
    title: document.title,
    inputs,
    buttons,
    body: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 1200)
  };
}
"""


def _connect(p, port: int):
    return p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")


def status(port: int = 9222) -> dict:
    with sync_playwright() as p:
        try:
            browser = _connect(p, port)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"未连接浏览器（{type(e).__name__}）"}
        pages = []
        for ctx in browser.contexts:
            for pg in ctx.pages:
                try:
                    pages.append({"url": pg.url, "title": pg.title()})
                except Exception:
                    continue
        return {"ok": True, "pages": pages}


def open_seller(port: int = 9222, url: str = SELLER_URL) -> dict:
    with sync_playwright() as p:
        try:
            browser = _connect(p, port)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"未连接浏览器（{type(e).__name__}）"}
        ctx = browser.contexts[0]
        page = ctx.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        keep_open = False
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3500)
            title = page.title()
            body = page.evaluate("() => (document.body.innerText || '').replace(/\\s+/g, ' ')")
            need_login = any(k in page.url.lower() for k in ("login", "signin")) or "登录" in body[:300]
            if need_login:
                for sel in ("text=登录", "button:has-text('登录')"):
                    try:
                        loc = page.locator(sel).first
                        if loc.count() > 0:
                            loc.click(timeout=3000)
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        continue
            keep_open = need_login
            page.screenshot(path=str(DATA / "ae_seller.png"))
            page.bring_to_front()
            return {
                "ok": True,
                "need_login": need_login,
                "url": page.url,
                "title": title,
                "body": body[:300],
                "message": "未登录，请在打开的窗口登录速卖通卖家后台" if need_login else "已进入卖家后台",
            }
        finally:
            if not keep_open:
                page.close()


def fill_preview(title: str, image_url: str = "", port: int = 9222, dry_run: bool = True) -> dict:
    """填空演练：填标题 + 传主图，不点保存。"""
    import urllib.request

    img_path = DATA / "upload_main.jpg"
    if image_url:
        jpg_url = image_url.split("_.webp")[0]
        try:
            req = urllib.request.Request(jpg_url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://detail.1688.com/"})
            with urllib.request.urlopen(req, timeout=20) as r, open(img_path, "wb") as f:
                f.write(r.read())
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"图片下载失败：{type(e).__name__}"}

    with sync_playwright() as p:
        try:
            browser = _connect(p, port)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"未连接浏览器（{type(e).__name__}）"}
        ctx = browser.contexts[0]
        page = next((x for x in ctx.pages if "product_publish" in x.url), None)
        if page is None:
            return {"ok": False, "message": "请先打开「发布商品」页面"}
        page.bring_to_front()
        step = []
        try:
            # 清掉可能残留的图片库弹窗
            for label in ("确认上传", "取消"):
                try:
                    btn = page.get_by_text(label, exact=True).first
                    if btn.count() > 0 and btn.is_visible():
                        btn.click(timeout=2500)
                        page.wait_for_timeout(1500)
                        step.append(f"关闭残留弹窗({label})")
                        break
                except Exception:
                    continue

            box = page.get_by_placeholder("请输入标题").first
            box.click(timeout=5000)
            box.fill(title)
            step.append("标题已填")
            page.wait_for_timeout(800)

            if image_url and img_path.exists():
                uploaded = False
                try:
                    with page.expect_file_chooser(timeout=6000) as fc:
                        page.get_by_text("上传图片", exact=True).first.click()
                    fc.value.set_files(str(img_path))
                    uploaded = True
                    step.append("主图已上传")
                    page.wait_for_timeout(4500)
                except Exception:
                    files = page.locator('input[type="file"]')
                    if files.count() > 0:
                        files.first.set_input_files(str(img_path))
                        uploaded = True
                        step.append("主图已上传(直填)")
                        page.wait_for_timeout(4000)
                if not uploaded:
                    step.append("未找到上传入口")

                # 图片库确认弹窗
                try:
                    confirm = page.get_by_text("确认上传", exact=True).first
                    if confirm.count() > 0:
                        confirm.click(timeout=4000)
                        step.append("已确认上传")
                        page.wait_for_timeout(3000)
                except Exception:
                    pass

            page.screenshot(path=str(DATA / "ae_filled.png"))
            return {"ok": True, "steps": step, "dry_run": dry_run,
                    "title_len": len(title), "image": str(img_path)}
        except Exception as e:  # noqa: BLE001
            page.screenshot(path=str(DATA / "ae_filled_error.png"))
            return {"ok": False, "steps": step, "message": f"{type(e).__name__}: {e}"}


def dump_publish_form(port: int = 9222) -> dict:
    """打开「发布商品」表单并导出结构（不保存、不提交）。"""
    out = DATA / "ae_publish_dump.json"
    with sync_playwright() as p:
        try:
            browser = _connect(p, port)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"未连接浏览器（{type(e).__name__}）"}
        ctx = browser.contexts[0]
        page = next((pg for pg in ctx.pages if "csp.aliexpress.com" in pg.url), None)
        if page is None:
            page = ctx.new_page()
            page.goto(SELLER_URL, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
        try:
            page.bring_to_front()
            clicked = []
            before = len(ctx.pages)
            for text in ("商品管理", "发布商品"):
                try:
                    loc = page.get_by_text(text, exact=False).first
                    if loc.count() > 0:
                        loc.click(timeout=4000)
                        clicked.append(text)
                        page.wait_for_timeout(2500)
                except Exception:
                    continue
            if len(ctx.pages) > before:
                page = ctx.pages[-1]
                page.bring_to_front()
                page.wait_for_timeout(3000)
            data = page.evaluate(DUMP_JS)
            # csp 后台是微前端，表单可能在 iframe 里
            frames = []
            for fr in page.frames:
                try:
                    d = fr.evaluate(DUMP_JS)
                    d["frame_url"] = fr.url
                    frames.append(d)
                except Exception:
                    continue
            data["frames"] = frames
            data["clicked"] = clicked
            all_inputs = data["inputs"] + [i for f in frames if f["url"] != data["url"] for i in f["inputs"]]
            data["input_total"] = len(all_inputs)
            out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            page.screenshot(path=str(DATA / "ae_publish.png"), full_page=False)
            return {"ok": True, "file": str(out), "url": data["url"], "title": data["title"],
                    "inputs": data["input_total"], "clicked": clicked,
                    "frames": [f["url"] for f in frames]}
        finally:
            page.close()
