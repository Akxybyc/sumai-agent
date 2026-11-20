"""1688 采集器（RPA 驱动）：通过 CDP 接管用户 Chrome，读取搜索结果与商品详情。

设计原则：
- 只读公开商品页，不碰订单/买家数据；
- 用启发式提取（链接 + 文本），不依赖易变的 class 名；
- 遇到登录/滑块立即返回，交由人工处理，不硬闯。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

BASE = Path(__file__).resolve().parent
DATA_DIR = BASE.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

JS_EXTRACT = """
() => {
  const out = [];
  const seen = new Set();
  document.querySelectorAll('a[href*="offer/"]').forEach(a => {
    const m = (a.href || '').match(/offer\\/(\\d+)\\.html/);
    if (!m || seen.has(m[1])) return;
    let node = a;
    let text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
    // 1688 的商品卡通常就是整个 <a>；文本太短才向上找一层
    for (let i = 0; i < 3 && text.length < 30 && node.parentElement; i++) {
      const p = node.parentElement;
      if (p.querySelectorAll('a[href*="offer/"]').length > 2) break;
      node = p;
      text = (node.innerText || '').replace(/\\s+/g, ' ').trim();
    }
    if (text.length < 20) return;
    const lines = (node.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
    const img = node.querySelector('img') || a.querySelector('img');
    seen.add(m[1]);
    out.push({
      id: m[1],
      url: a.href.split('?')[0],
      anchor: (a.getAttribute('title') || '').trim(),
      img: img ? (img.src || img.getAttribute('data-src') || '') : '',
      text: text.slice(0, 600),
      lines: lines.slice(0, 14)
    });
  });
  return out;
}
"""


def _encode_keyword(keyword: str) -> str:
    """1688 搜索接口按 GBK 解析 keywords，UTF-8 会变乱码。"""
    try:
        return quote(keyword.encode("gbk"))
    except Exception:
        return quote(keyword)


def _num(text: str) -> float:
    text = text.replace(",", "")
    try:
        return float(text)
    except Exception:
        return 0.0


def _parse_sales(text: str) -> int:
    m = re.search(r"(?:已售|成交|销量|月销)\s*([\d.]+)\s*(万)?", text)
    if not m:
        # 1688 卡片常见 "2100+件"，用 50 作为阈值排除起批量（10+件 / 2+件）
        for mm in re.finditer(r"([\d.]+)\s*(万)?\s*\+?\s*件", text):
            val = _num(mm.group(1))
            if val >= 50 or mm.group(2):
                return int(val * 10000) if mm.group(2) else int(val)
        return 0
    val = _num(m.group(1))
    return int(val * 10000) if m.group(2) else int(val)


def _parse_collectors(text: str) -> int:
    m = re.search(r"([\d.]+)\s*(万)?\s*人(?:已采|采购|收藏|加购)", text)
    if not m:
        return 0
    val = _num(m.group(1))
    return int(val * 10000) if m.group(2) else int(val)


def _parse_repurchase(text: str) -> float:
    """1688 新版卡片用「回头率」替代了采集人数，是更可靠的品质信号。"""
    m = re.search(r"回头率\s*([\d.]+)\s*%", text)
    return _num(m.group(1)) if m else 0.0


def _parse_price(text: str) -> float:
    for pat in (r"¥\s*([\d,]+\.?\d*)", r"([\d.]+)\s*元"):
        m = re.search(pat, text)
        if m:
            return _num(m.group(1))
    return 0.0


def _parse_title(item: dict) -> str:
    title = (item.get("anchor") or "").strip()
    if len(title) >= 8:
        return title
    lines = item.get("lines") or []
    for line in lines:
        if len(line) >= 8 and "¥" not in line and "件" not in line and "包邮" not in line:
            return line[:120]
    return (item.get("text") or "")[:120]


def _parse_supplier(lines: list[str]) -> str:
    for line in reversed(lines or []):
        if any(k in line for k in ("有限公司", "厂", "商行", "经营部", "合作社")):
            return line[:60]
    return ""


def _connect(p, port: int):
    return p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")


def collect_search(keyword: str, pages: int = 1, limit: int = 20, port: int = 9222) -> dict:
    """采集搜索结果，返回标准化商品列表。"""
    started = time.time()
    with sync_playwright() as p:
        try:
            browser = _connect(p, port)
        except Exception as e:  # noqa: BLE001
            return {
                "ok": False,
                "need_launch": True,
                "message": f"未连接到调试端口 {port}，请先启动带调试端口的 Chrome（{type(e).__name__}）",
            }
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        page.set_viewport_size({"width": 1440, "height": 900})
        keep_open = False
        try:
            url = f"https://s.1688.com/selloffer/offer_search.htm?keywords={_encode_keyword(keyword)}"
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)

            if "login" in page.url or page.locator("text=请登录").count() > 0:
                keep_open = True
                page.bring_to_front()
                page.screenshot(path=str(DATA_DIR / "1688_need_login.png"))
                return {"ok": False, "need_login": True,
                        "message": "1688 未登录，请在打开的浏览器里登录后重试"}

            if "punish" in page.url or "验证码" in (page.title() or ""):
                keep_open = True
                page.bring_to_front()
                page.screenshot(path=str(DATA_DIR / "1688_need_verify.png"))
                return {"ok": False, "need_verify": True,
                        "message": "触发 1688 滑块验证，请在打开的 Chrome 窗口里拖动滑块完成验证，然后重试"}

            raw = []
            for page_no in range(pages):
                for _ in range(3):
                    page.mouse.wheel(0, 1400)
                    page.wait_for_timeout(700)
                raw.extend(page.evaluate(JS_EXTRACT))
                if page_no + 1 < pages:
                    nxt = page.locator("a:has-text('下一页')").first
                    if nxt.count() == 0:
                        break
                    nxt.click()
                    page.wait_for_timeout(2500)

            seen, items = set(), []
            for r in raw:
                if r["id"] in seen:
                    continue
                seen.add(r["id"])
                text = r.get("text", "")
                price = _parse_price(text)
                if price <= 0:
                    continue
                items.append({
                    "id": f"1688-{r['id']}",
                    "offer_id": r["id"],
                    "url": r["url"],
                    "title": _parse_title(r),
                    "price_cny": price,
                    "sales_30d": _parse_sales(text),
                    "collectors": _parse_collectors(text),
                    "repurchase_rate": _parse_repurchase(text),
                    "supplier": _parse_supplier(r.get("lines") or []),
                    "rating": 0,
                    "weight_g": 0,
                    "image": r.get("img", ""),
                    "image_count": 1,
                    "skus": [],
                    "category": keyword,
                    "source": "rpa1688",
                    "raw_text": text[:200],
                })
                if len(items) >= limit:
                    break

            page.screenshot(path=str(DATA_DIR / "1688_search.png"), full_page=False)
            out = DATA_DIR / f"1688_{re.sub(r'[^\\w\\u4e00-\\u9fa5]', '_', keyword)}.json"
            out.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True, "count": len(items), "items": items,
                    "file": str(out), "elapsed": round(time.time() - started, 1)}
        finally:
            if not keep_open:
                page.close()


DETAIL_JS = """
() => {
  const txt = (el) => el ? (el.innerText || '').replace(/\\s+/g, ' ').trim() : '';
  const imgs = Array.from(document.querySelectorAll('img')).map(i => i.src)
    .filter(s => s && s.includes('cbu01') && /\\.(jpg|jpeg|png|webp)/i.test(s));
  const skuBtns = Array.from(document.querySelectorAll('button.sku-filter-button')).map(b => txt(b));
  return {
    title: document.title,
    h1: txt(document.querySelector('h1')),
    body: (document.body.innerText || '').replace(/\\s+/g, ' '),
    skus: Array.from(new Set(skuBtns)),
    images: Array.from(new Set(imgs)).slice(0, 10),
    skuBlock: txt(document.querySelector('.module-od-sku-selection'))
  };
}
"""

ATTR_KEYS = [
    "内胆材质", "外壳材质", "材质", "品牌", "功能", "保温性能", "货号", "容量",
    "颜色", "杯盖材质", "适用人群", "适用场景", "风格", "包装规格", "加工定制",
]


def _parse_attributes(body: str) -> dict:
    attrs = {}
    for key in ATTR_KEYS:
        m = re.search(rf"{key}\s+([^\s]{{1,28}})", body)
        if m:
            attrs[key] = m.group(1)
    return attrs


def collect_detail(url: str, port: int = 9222) -> dict:
    """采集单个商品详情：标题、价格、SKU、图片、重量尺寸、属性、评分。"""
    with sync_playwright() as p:
        try:
            browser = _connect(p, port)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"未连接到调试端口 {port}（{type(e).__name__}）"}
        ctx = browser.contexts[0] if browser.contexts else browser.new_context()
        page = ctx.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            for _ in range(3):
                page.mouse.wheel(0, 1200)
                page.wait_for_timeout(600)

            d = page.evaluate(DETAIL_JS)
            body = d.get("body", "")
            title = re.sub(r"\s*-\s*阿里巴巴.*$", "", d.get("title", "")).strip()

            weight, dims = 0, {}
            m = re.search(
                r"长\(cm\)\s*宽\(cm\)\s*高\(cm\)\s*体积\(cm³\)\s*重量\(g\)\s*"
                r"([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", body)
            if m:
                dims = {"length_cm": float(m.group(1)), "width_cm": float(m.group(2)),
                        "height_cm": float(m.group(3)), "weight_g": float(m.group(5))}
                weight = int(float(m.group(5)))

            price = 0.0
            pm = re.search(r"¥\s*([\d,]+\.?\d*)", d.get("skuBlock", "") or "")
            if not pm:
                pm = re.search(r"¥\s*([\d,]+\.?\d*)", body)
            if pm:
                price = _num(pm.group(1))

            rating, reviews = 0.0, 0
            rm = re.search(r"商品评价\s*([\d.]+)\s*([\d+]+)条评价", body)
            if rm:
                rating, reviews = _num(rm.group(1)), int(rm.group(2).rstrip("+"))

            stock = 0
            sm = re.search(r"库存(\d+)个", body)
            if sm:
                stock = int(sm.group(1))

            return {
                "ok": True,
                "title": title,
                "supplier": d.get("h1", ""),
                "price_cny": price,
                "price_ladder": sorted({_num(x) for x in re.findall(r"¥\s*([\d,]+\.?\d*)", body)})[:6],
                "weight_g": weight,
                "dimensions": dims,
                "stock": stock,
                "skus": d.get("skus", [])[:12],
                "images": d.get("images", [])[:8],
                "attributes": _parse_attributes(body),
                "rating": rating,
                "reviews": reviews,
            }
        finally:
            page.close()


if __name__ == "__main__":
    import sys
    kw = sys.argv[1] if len(sys.argv) > 1 else "保温杯"
    res = collect_search(kw, pages=1, limit=20)
    print(json.dumps({k: v for k, v in res.items() if k != "items"}, ensure_ascii=False))
    if res.get("items"):
        for it in res["items"][:5]:
            print(it["price_cny"], it["sales_30d"], it["collectors"], it["title"][:40])
