"""趋势驱动选品：速卖通实时热销 → 反推可售价带 → 1688 找货源 → 打分排序。

逻辑：
1) 速卖通前台拿 top 销量商品的价格分布（取中位数当"主流可售价"）
2) 目标采购成本 = 主流可售价 × 汇率 × 成本占比（默认 35%）
3) 1688 搜同款，按「销量 × 价格达标 × 复购」打分
"""

from __future__ import annotations

import statistics

import rpa1688
import trend_ae

LAST_PICKS = {"items": [], "fetched_at": ""}

RATE = 7.2          # USD → CNY 粗算
COST_RATIO = 0.35   # 采购成本占售价比例（全托管留利润）


def price_band(items: list[dict]) -> dict:
    prices = [i["price"] for i in items if i.get("price", 0) > 0.5]
    solds = [i.get("sold", 0) for i in items]
    if not prices:
        return {"median": 0, "low": 0, "high": 0, "top_sold": max(solds or [0])}
    return {
        "median": round(statistics.median(prices), 2),
        "low": round(min(prices), 2),
        "high": round(max(prices), 2),
        "top_sold": max(solds or [0]),
    }


def pick(keyword_en: str, keyword_cn: str, limit: int = 5, port: int = 9222) -> dict:
    trend = trend_ae.search(keyword_en, port=port, limit=20)
    if not trend.get("ok"):
        return {"ok": False, "message": "速卖通趋势抓取失败，检查浏览器登录/网络"}

    band = price_band(trend["items"])
    target_cost = round(band["median"] * RATE * COST_RATIO, 2)

    import time as _t

    items = []
    last = {}
    for attempt in range(2):
        last = rpa1688.collect_search(keyword_cn, pages=1, limit=20, port=port)
        items = last.get("items") or []
        if items or last.get("need_verify") or last.get("need_login"):
            break
        _t.sleep(4)
    if not items:
        hint = ("触发 1688 滑块验证，请在调试 Chrome 窗口里完成验证后重试"
                if last.get("need_verify") else
                "1688 未登录，请先在调试 Chrome 里登录" if last.get("need_login") else
                "1688 没搜到货源（可能被限流，稍等再试或换个更具体的关键词）")
        return {"ok": False, "message": hint, "need_verify": bool(last.get("need_verify")),
                "band": band, "target_cost": target_cost, "keyword_cn": keyword_cn}

    for it in items:
        price = float(it.get("price_cny") or it.get("price") or 0)
        sales = int(it.get("sales_30d") or it.get("sales") or 0)
        repurchase = float(it.get("repurchase_rate") or it.get("repurchase") or 0)
        fit = 1.0 if (target_cost and 0 < price <= target_cost) else 0.55
        import math
        sales_score = min(math.log10(max(sales, 1)) / 5, 1.0) * 55      # 1万→44分, 10万→55分
        rep_score = min(repurchase, 60) / 60 * 20
        price_score = 25 * fit if fit == 1.0 else 25 * 0.5
        score = sales_score + rep_score + price_score
        it["_score"] = round(score, 1)
        it["_fits_cost"] = bool(target_cost and 0 < price <= target_cost)
        it["_margin"] = round((band["median"] * RATE - price) / (band["median"] * RATE) * 100, 1) if band["median"] else 0

    items.sort(key=lambda x: x["_score"], reverse=True)

    LAST_PICKS["items"] = items[:max(limit, 5)]
    LAST_PICKS["fetched_at"] = trend["fetched_at"]

    return {
        "ok": True,
        "keyword_en": keyword_en,
        "keyword_cn": keyword_cn,
        "fetched_at": trend["fetched_at"],
        "band": band,
        "target_cost": target_cost,
        "candidates": items[:limit],
        "total_found": len(items),
    }
