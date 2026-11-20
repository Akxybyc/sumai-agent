"""供货价计算规则（用户指定）。

- 成本 0~10 元（不含 10）：不套公式，必须问客户自己定
- 成本 ≥10 元：(商品原价 + 国内运费 + 5 元打包费) × 2
"""

from __future__ import annotations

PACKAGING = 5.0
MULTIPLIER = 2.0
MANUAL_THRESHOLD = 10.0   # 低于此值需客户手动给价


def calc(cost_cny: float, freight_cny: float = 0.0) -> dict:
    cost = float(cost_cny or 0)
    freight = float(freight_cny or 0)

    if cost <= 0:
        return {"price": 0.0, "need_manual": True, "formula": "无成本数据",
                "reason": "缺成本，需客户给供货价"}

    if cost < MANUAL_THRESHOLD:
        return {
            "price": 0.0,
            "need_manual": True,
            "formula": "-",
            "reason": f"成本 {cost:.2f} 元在 0~10 元区间，按规则需客户自己定供货价",
            "ask": f"这款成本 {cost:.2f} 元，你想定多少供货价？",
        }

    price = round((cost + freight + PACKAGING) * MULTIPLIER, 2)
    return {
        "price": price,
        "need_manual": False,
        "formula": f"({cost:.2f} + {freight:.2f} + {PACKAGING:.0f}) × {MULTIPLIER:.0f} = {price:.2f}",
        "reason": "",
    }
