"""妙手开放平台 API 客户端。

签名（官方文档 4.2）：
    sign = HMAC-SHA256(appSecret, appSecret + path + timestamp + appKey + bodyJson + appSecret)  小写 hex
Header：x-app-key / x-timestamp / x-sign（timestamp 秒级，±300s 有效）

文档：https://s.apifox.cn/fd54e57e-9b98-4c34-bada-306221c39e68
基础域名：https://openapi-erp.91miaoshou.com
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"
BASE = "https://openapi-erp.91miaoshou.com"


def _cfg() -> dict:
    try:
        s = json.loads((DATA / "settings.json").read_text(encoding="utf-8"))
        return s.get("miaoshou_api") or {}
    except Exception:
        return {}


def make_sign(app_secret: str, path: str, ts: str, app_key: str, body: str) -> str:
    raw = f"{app_secret}{path}{ts}{app_key}{body}{app_secret}"
    return hmac.new(app_secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()


_LAST_CALL = {"ts": 0.0}
_MIN_INTERVAL = 1.15  # 妙手限流：账户级 1 次/秒


def call(path: str, payload: dict | None = None, timeout: int = 40, cfg: dict | None = None) -> dict:
    cfg = cfg or _cfg()
    app_key = cfg.get("app_id") or ""
    app_secret = cfg.get("app_secret") or ""
    base = (cfg.get("base_url") or BASE).rstrip("/")
    if not app_key or not app_secret:
        return {"ok": False, "message": "未配置妙手 AppKey/AppSecret（settings.json → miaoshou_api）"}

    # 节流，避免 429
    gap = time.time() - _LAST_CALL["ts"]
    if gap < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - gap)
    _LAST_CALL["ts"] = time.time()

    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) if payload is not None else ""
    ts = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "x-app-key": app_key,
        "x-timestamp": ts,
        "x-sign": make_sign(app_secret, path, ts, app_key, body),
    }
    req = urllib.request.Request(
        base + path,
        data=body.encode("utf-8") if body else b"{}",
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", "ignore")
            try:
                data = json.loads(text)
            except Exception:
                data = {"raw": text[:400]}
            code = data.get("code", data.get("errno", data.get("status")))
            ok = (str(code).lower() in ("0", "200", "success")) or data.get("success") is True
            return {"ok": ok, "status": r.status, "code": code, "data": data,
                    "message": data.get("msg") or data.get("message") or ""}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "ignore")[:400]
        return {"ok": False, "status": e.code, "message": f"HTTP {e.code}: {txt}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}


# ---------- 接口 ----------
def get_shop_list(platform: str = "tiktok") -> dict:
    """POST /open/v1/product/shop/shop/get_shop_list（只读，用于验签）"""
    return call("/open/v1/product/shop/shop/get_shop_list",
                {"platform": platform, "pageNo": 1, "pageSize": 20})


def ping() -> dict:
    return get_shop_list("tiktok")


if __name__ == "__main__":
    print(json.dumps(ping(), ensure_ascii=False)[:600])


# ---------- 公共采集箱 ----------
def collect_by_links(links: list[str]) -> dict:
    """通过货源链接采集（最多 50 条），返回 {货源ID: 采集箱detailId}。"""
    return call("/open/v1/product/common_collect_box/common_collect_box/fetch_item",
                {"collectLinks": links[:50]})


def list_collect_box(page_no: int = 1, page_size: int = 20, tab: str = "all",
                     source_item_id: str = "") -> dict:
    """公共采集箱列表。tab: all/noClaimed/claimed/collectFail/collectSuccess"""
    body = {"pageNo": page_no, "pageSize": page_size, "filter": {"tabPaneName": tab}}
    if source_item_id:
        body["filter"]["sourceItemIdKeyword"] = source_item_id
    return call("/open/v1/product/common_collect_box/common_collect_box/get_common_collect_box_list", body)


def list_all_sources(max_pages: int = 20, tab: str = "all") -> dict:
    """遍历公共采集箱，返回 {货源ID: detailId}，用于采集前去重。"""
    found: dict[str, int] = {}
    total = 0
    for page in range(1, max_pages + 1):
        r = list_collect_box(page, 500, tab)
        d = (r.get("data") or {}).get("data") or {}
        items = d.get("detailList") or []
        total = d.get("total") or total
        if not items:
            break
        for it in items:
            did = it.get("commonCollectBoxDetailId")
            for src in (it.get("sourceList") or []):
                sid = str(src.get("sourceItemId") or "")
                if sid:
                    found[sid] = did
        if len(items) < 500 or (total and page * 500 >= total):
            break
    return {"ok": True, "total": total, "sources": found}


def batch_delete_box(detail_ids: list[int], chunk: int = 50) -> dict:
    """批量删除公共采集箱产品（自动分批 + 节流）。"""
    path = "/open/v1/product/common_collect_box/common_collect_box/batch_delete_common_collect_box_detail"
    deleted = 0
    errors = []
    for i in range(0, len(detail_ids), chunk):
        part = detail_ids[i:i + chunk]
        r = call(path, {"commonCollectBoxDetailIds": part})
        if r.get("ok"):
            deleted += len(part)
        else:
            errors.append(r.get("message") or "删除失败")
    return {"ok": not errors, "deleted": deleted, "errors": errors}


# ---------- AI 公共服务：翻译 ----------
def translate_lang_config(payload: dict | None = None) -> dict:
    """获取支持的翻译语言配置。"""
    return call("/open/v1/product/common/translate/get_support_language_config",
                payload or {})


def translate_image(image_urls: list[str], source: str = "zh", target: str = "en",
                    platform: str = "ali", no_translate: list[str] | None = None) -> dict:
    """图片翻译（AI 覆盖重排）。platform: ali / aeAi / tosoiot / ykt。"""
    body = {
        "imageUrls": image_urls[:20],
        "sourceLang": source,
        "targetLang": target,
        "translatePlatform": platform,
    }
    if no_translate:
        body["noTranslateImageTextOptions"] = no_translate
    return call("/open/v1/product/common/translate/translate_image", body)


def translate_strings(texts: list[str], source: str = "zh", target: str = "en",
                      chunk: int = 25) -> dict:
    """用妙手「产品翻译」批量翻文本（值），返回 {原文: 译文}。

    接口挂在 tiktok 命名空间，但实测对速卖通全托管内容同样可用，且不计图片额度。
    """
    out: dict[str, str] = {}
    for i in range(0, len(texts), chunk):
        part = [t for t in texts[i:i + chunk] if t]
        if not part:
            continue
        body = {
            "sourceLanguage": source,
            "targetLanguage": target,
            "isTranslateSkuItemNum": 0,
            "isTranslateSkuProperty": 0,
            "collectItemInfo": {
                "productAttributes": [
                    {"attributeName": f"A{j}", "attributeValues": [{"valueName": t}]}
                    for j, t in enumerate(part)
                ]
            },
        }
        r = call("/open/v1/product/collect_box/tiktok/collect_box/translate_collect_item_info", body)
        data = (r.get("data") or {}).get("data") or {}
        info = data.get("collectItemInfo") or {}
        attrs = info.get("productAttributes") or []
        for j, t in enumerate(part):
            if j < len(attrs):
                vals = attrs[j].get("attributeValues") or []
                if vals:
                    out[t] = (vals[0].get("valueName") or "").strip()
        if not r.get("ok"):
            return {"ok": False, "map": out, "message": r.get("message") or "翻译失败"}
    return {"ok": True, "map": {k: v for k, v in out.items() if v}}


def edit_collect_box_item(detail_id: int, fields: dict, oss_md5: str) -> dict:
    """改公共采集箱商品（标题/描述/价格/库存/颜色名…）。必传 ossMd5（先 GET 详情拿）。"""
    body = {"commonCollectBoxDetailId": int(detail_id), "ossMd5": oss_md5,
            "editCommonCollectBoxDetail": fields}
    return call("/open/v1/product/common_collect_box/common_collect_box/edit_common_collect_box_detail", body)


def write_english_to_box(detail_ids: list[int] | None = None, dry_run: bool = False) -> dict:
    """把公共采集箱商品的标题/描述/颜色属性名改成英文（认领前写入，省掉编辑页翻译）。"""
    items, total = [], 0
    for page in range(1, 6):
        r = list_collect_box(page, 100, "all")
        d = (r.get("data") or {}).get("data") or {}
        lst = d.get("detailList") or []
        items.extend(lst)
        total = d.get("total") or total
        if len(lst) < 100:
            break

    targets = [x for x in items if str(x.get("status")) == "success"]
    if detail_ids:
        want = {int(i) for i in detail_ids}
        targets = [x for x in targets if int(x.get("commonCollectBoxDetailId") or 0) in want]

    done, skipped, errors = 0, 0, []
    for it in targets:
        did = it.get("commonCollectBoxDetailId")
        try:
            q = call("/open/v1/product/common_collect_box/common_collect_box/get_common_collect_box_detail",
                     {"commonCollectBoxDetailId": did})
            data = (q.get("data") or {}).get("data") or {}
            det = data.get("editCommonCollectBoxDetail") or {}
            md5 = data.get("ossMd5")
            title = det.get("title") or ""

            # 原标题已是英文 → 跳过（判断必须用原标题，不能用译文）
            if not any("\u4e00" <= c <= "\u9fff" for c in title):
                skipped += 1
                continue

            texts = [t for t in (title, det.get("notesText")) if t]
            mp = translate_strings(texts).get("map") or {}
            en_title = mp.get(title) or title

            fields = {
                "title": en_title[:250],
                "price": det.get("price") or 1,
                "stock": min(int(det.get("stock") or 1000), 99999),
                "colorPropName": "Color",
            }
            if det.get("notesText"):
                fields["notesText"] = (mp.get(det.get("notesText")) or det["notesText"])[:60000]

            if dry_run:
                done += 1
                continue

            w = edit_collect_box_item(did, fields, md5)
            if w.get("ok"):
                done += 1
            else:
                errors.append({"id": did, "msg": (w.get("data") or {}).get("message") or w.get("message")})
        except Exception as e:  # noqa: BLE001
            errors.append({"id": did, "msg": f"{type(e).__name__}: {e}"})

    return {"ok": not errors, "total": len(targets), "done": done, "skipped": skipped,
            "errors": errors[:5], "dry_run": dry_run,
            "message": f"{'预演' if dry_run else '已写入'} {done} 条英文（跳过已是英文 {skipped} 条）"}
