"""把 1688 中文属性译成速卖通上架用的英文属性。"""

from __future__ import annotations

import re

KEY_MAP = {
    "材质": "Material", "具体材质": "Specific Material", "品牌": "Brand",
    "功能": "Function", "货号": "Item No.", "容量": "Capacity", "颜色": "Color",
    "风格": "Style", "加工定制": "Customized", "产地": "Origin", "图案": "Pattern",
    "规格": "Specification", "适用场景": "Usage Scenario", "商品特性": "Feature",
    "适用范围": "Application", "收纳场景": "Storage Scenario", "箱装数量": "Packing Quantity",
    "毛重": "Gross Weight", "开合方式": "Opening Type", "是否进口": "Imported",
    "塑料新料占比": "New Plastic Ratio", "价格段": "Price Range", "专利": "Patent",
    "主要下游平台": "Main Platform", "主要销售地区": "Main Sales Region",
    "贸易属性": "Trade Attribute", "是否跨境出口专供货源": "Cross-border Supply",
    "有可授权的自有品牌": "Authorized Brand", "加印LOGO": "Custom Logo",
    "产品上市时间": "Launch Date", "产品类别": "Product Category", "型号": "Model",
    "是否原箱": "Original Box",
}

VALUE_MAP = {
    "塑料": "Plastic", "防尘": "Dust-proof", "现代简约": "Modern Minimalist",
    "否": "No", "是": "Yes", "其他": "Others", "纯色": "Solid Color",
    "特大号": "Extra Large", "大号": "Large", "中号": "Medium", "小号": "Small",
    "100%新料": "100% New Material", "内贸+外贸": "Domestic & Export",
    "不可以": "No", "可以": "Yes", "无": "None", "有": "Yes",
    "简约": "Minimalist", "现代": "Modern", "北欧": "Nordic",
    "中国大陆": "Mainland China", "浙江": "Zhejiang, China", "广东": "Guangdong, China",
    "亚马逊": "Amazon", "速卖通": "AliExpress", "独立站": "Independent Site",
    "欧洲": "Europe", "东南亚": "Southeast Asia", "北美": "North America",
    "浴室": "Bathroom", "桌上": "Desktop", "卫生间": "Bathroom",
    "无盖": "No Lid", "翻盖": "Flip Lid", "抽屉": "Drawer", "带分格": "With Compartments",
    "日用": "Daily Use", "家居": "Home",
}

COLOR_MAP = {
    "白色": "White", "黑色": "Black", "灰色": "Gray", "浅灰色": "Light Gray",
    "黄色": "Yellow", "鹅黄色": "Goose Yellow", "浅绿色": "Light Green",
    "绿色": "Green", "蓝色": "Blue", "粉色": "Pink", "红色": "Red",
    "奶油色": "Cream", "米色": "Beige", "透明": "Clear", "卡其色": "Khaki",
    "深卡其色": "Dark Khaki", "棕色": "Brown", "原木色": "Natural Wood",
}

_CJK = re.compile(r"[\u4e00-\u9fff]")


def has_cjk(s: str) -> bool:
    return bool(_CJK.search(s or ""))


MATERIAL_HINTS = ["ABS", "PP", "PS", "PC", "PVC", "TPE", "PE", "PET", "硅胶", "不锈钢", "玻璃", "木质"]


def _material(v: str) -> str:
    up = v.upper()
    tokens = [t for t in MATERIAL_HINTS if t in up]
    if "硅胶" in v:
        return "Silicone"
    if "不锈钢" in v:
        return "Stainless Steel"
    if "玻璃" in v:
        return "Glass"
    if "木" in v:
        return "Wood"
    if tokens:
        return " ".join(tokens[:2]) + (" Plastic" if "塑料" in v else "")
    if "塑料" in v:
        return "Plastic"
    return ""


def _translate_value(v: str) -> str:
    """整值精确匹配 → 颜色逐词替换 → 仍含中文则返回空（跳过该属性）。"""
    v = (v or "").strip().rstrip("。；;，,")
    if not v:
        return ""
    if not has_cjk(v):
        return v
    if v in VALUE_MAP:
        return VALUE_MAP[v]
    # 颜色串：白色洞洞板置物架、奶油色… → White / Cream
    if "色" in v and ("、" in v or "/" in v or "，" in v):
        parts = re.split(r"[、/，,]", v)
        out = []
        for p in parts:
            p = p.strip()
            hit = next((en for cn, en in COLOR_MAP.items() if cn in p), None)
            if hit and hit not in out:
                out.append(hit)
        if out:
            return ", ".join(out)
    # 组合值：内贸+外贸、100%新料
    for cn, en in VALUE_MAP.items():
        if v == cn:
            return en
    # 材质类兜底
    m = _material(v)
    if m:
        return m.strip()

    # 逐段替换
    parts = re.split(r"[+＋]", v)
    if len(parts) > 1:
        outs = [VALUE_MAP.get(p.strip(), "") for p in parts]
        if all(outs):
            return " & ".join(outs)
    return ""


def translate(attrs: dict) -> dict:
    out: dict[str, str] = {}
    for k, v in (attrs or {}).items():
        if not isinstance(v, str):
            v = str(v)
        key = KEY_MAP.get(k.strip(), k.strip())
        # 已是英文的键值原样保留
        if not has_cjk(key) and not has_cjk(v):
            out[key] = v
            continue
        val = _translate_value(v)
        if has_cjk(key):
            # 无法映射的中文键：跳过（避免把中文带上架）
            continue
        if val:
            out[key] = val
    # 去重（同名键保留第一个）
    return out
