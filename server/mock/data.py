"""Mock 数据层：模拟 1688 开放平台返回的商品与速卖通发布结果。

真实接入后，本文件由 tools/a1688.py 的 API 驱动替换，接口形状保持不变。
"""

CANDIDATES = [
    {
        "id": "1688-943210226045",
        "title": "304不锈钢保温杯 便携迷你口袋杯 商务礼品杯 定制logo",
        "category": "家居用品>厨房吧台用品>饮具>保温杯",
        "price_cny": 23.80,
        "sales_30d": 12800,
        "collectors": 3260,
        "supplier": "永康市恒鑫工贸有限公司",
        "rating": 4.8,
        "weight_g": 260,
        "icon": "🥤",
        "hue": 205,
        "image_count": 6,
        "skus": ["纯白", "远山蓝", "金福红", "千里江山"],
    },
    {
        "id": "1688-887112003312",
        "title": "厨房多功能切菜神器 家用蔬菜切丝器 滚筒式刨丝器 手摇",
        "category": "家居用品>厨房用品>厨房工具>切菜器",
        "price_cny": 18.50,
        "sales_30d": 9600,
        "collectors": 2180,
        "supplier": "揭阳市榕城区优厨五金厂",
        "rating": 4.7,
        "weight_g": 420,
        "icon": "🔪",
        "hue": 160,
        "image_count": 8,
        "skus": ["三刀头标准款", "五刀头升级款"],
    },
    {
        "id": "1688-771209885541",
        "title": "桌面收纳盒 亚克力化妆品收纳 抽屉式置物架 办公室整理",
        "category": "家居用品>收纳整理>桌面收纳>收纳盒",
        "price_cny": 12.60,
        "sales_30d": 15400,
        "collectors": 4120,
        "supplier": "义乌市晶彩日用品有限公司",
        "rating": 4.9,
        "weight_g": 380,
        "icon": "🗃️",
        "hue": 268,
        "image_count": 7,
        "skus": ["透明小号", "透明大号", "奶白大号"],
    },
    {
        "id": "1688-665520114478",
        "title": "宠物自动饮水机 猫咪循环过滤水碗 静音大容量 跨境专供",
        "category": "宠物用品>宠物喂食器>饮水器",
        "price_cny": 42.00,
        "sales_30d": 7300,
        "collectors": 1980,
        "supplier": "深圳市萌宠智能科技有限公司",
        "rating": 4.8,
        "weight_g": 850,
        "icon": "🐱",
        "hue": 340,
        "image_count": 9,
        "skus": ["2L标准版", "3L智能版"],
    },
    {
        "id": "1688-554418900127",
        "title": "户外折叠椅 便携露营月亮椅 铝合金轻量化 钓鱼椅",
        "category": "运动户外>户外装备>露营家具>折叠椅",
        "price_cny": 58.00,
        "sales_30d": 6800,
        "collectors": 2450,
        "supplier": "宁波市野趣户外用品有限公司",
        "rating": 4.7,
        "weight_g": 1200,
        "icon": "🏕️",
        "hue": 120,
        "image_count": 10,
        "skus": ["卡其色", "军绿色", "黑色"],
    },
    {
        "id": "1688-443309776201",
        "title": "硅胶折叠水杯 户外便携伸缩杯 食品级旅行水杯 带盖",
        "category": "运动户外>户外装备>水具>折叠杯",
        "price_cny": 9.90,
        "sales_30d": 22300,
        "collectors": 5310,
        "supplier": "东莞市柔韧硅胶制品厂",
        "rating": 4.6,
        "weight_g": 150,
        "icon": "🥛",
        "hue": 190,
        "image_count": 6,
        "skus": ["500ml蓝色", "500ml粉色", "750ml灰色"],
    },
    {
        "id": "1688-332218664590",
        "title": "LED感应夜灯 人体感应小夜灯 USB充电 卧室走廊楼梯灯",
        "category": "家装灯饰>室内照明>夜灯",
        "price_cny": 15.80,
        "sales_30d": 18900,
        "collectors": 4720,
        "supplier": "中山市光屿照明有限公司",
        "rating": 4.8,
        "weight_g": 180,
        "icon": "💡",
        "hue": 45,
        "image_count": 8,
        "skus": ["暖光单只", "暖光两只装", "白光两只装"],
    },
    {
        "id": "1688-221107553318",
        "title": "厨房沥水篮 双层洗菜盆 不锈钢漏盆 家用水果篮",
        "category": "家居用品>厨房用品>洗菜盆>沥水篮",
        "price_cny": 21.00,
        "sales_30d": 8700,
        "collectors": 2030,
        "supplier": "潮州市潮安区顺发五金厂",
        "rating": 4.7,
        "weight_g": 460,
        "icon": "🥗",
        "hue": 100,
        "image_count": 5,
        "skus": ["22cm", "26cm", "30cm"],
    },
    {
        "id": "1688-110096442287",
        "title": "旅行收纳袋套装 衣物整理包 防水行李箱分装袋 七件套",
        "category": "箱包>旅行用品>收纳袋",
        "price_cny": 26.50,
        "sales_30d": 11200,
        "collectors": 3080,
        "supplier": "嘉兴市旅途箱包有限公司",
        "rating": 4.8,
        "weight_g": 320,
        "icon": "🧳",
        "hue": 215,
        "image_count": 9,
        "skus": ["七件套灰色", "七件套藏青", "七件套粉色"],
    },
    {
        "id": "1688-998874432110",
        "title": "手机支架 桌面懒人支架 铝合金折叠直播支架 跨境爆款",
        "category": "数码配件>手机配件>手机支架",
        "price_cny": 13.20,
        "sales_30d": 25600,
        "collectors": 6120,
        "supplier": "深圳市稳固科技有限公司",
        "rating": 4.6,
        "weight_g": 220,
        "icon": "📱",
        "hue": 250,
        "image_count": 7,
        "skus": ["银色", "深空灰"],
    },
    {
        "id": "1688-887765112034",
        "title": "电动咖啡打泡器 手持奶泡机 家用咖啡搅拌器 USB充电",
        "category": "家用电器>厨房小电>咖啡器具",
        "price_cny": 28.90,
        "sales_30d": 5400,
        "collectors": 1620,
        "supplier": "佛山市顺德区醇享电器厂",
        "rating": 4.7,
        "weight_g": 300,
        "icon": "☕",
        "hue": 25,
        "image_count": 6,
        "skus": ["白色", "黑色"],
    },
    {
        "id": "1688-776653221089",
        "title": "加厚珊瑚绒地垫 浴室防滑吸水垫 卧室床边毯 机洗",
        "category": "家纺>地毯地垫>浴室垫",
        "price_cny": 16.80,
        "sales_30d": 13600,
        "collectors": 3540,
        "supplier": "南通市暖居纺织有限公司",
        "rating": 4.8,
        "weight_g": 520,
        "icon": "🛁",
        "hue": 300,
        "image_count": 8,
        "skus": ["40x60灰色", "50x80灰色", "50x80米白"],
    },
]

# 类目英文映射（速卖通类目路径），真实场景由类目接口动态获取
CATEGORY_MAP = {
    "家居用品>厨房吧台用品>饮具>保温杯": "Home & Garden > Kitchen,Dining & Bar > Drinkware > Vacuum Flasks",
    "家居用品>厨房用品>厨房工具>切菜器": "Home & Garden > Kitchen,Dining & Bar > Kitchen Tools > Slicers",
    "家居用品>收纳整理>桌面收纳>收纳盒": "Home & Garden > Home Storage & Organization > Desktop Storage",
    "宠物用品>宠物喂食器>饮水器": "Pet Supplies > Dog Supplies > Feeding & Watering",
    "运动户外>户外装备>露营家具>折叠椅": "Sports & Entertainment > Camping & Hiking > Camping Furniture",
    "运动户外>户外装备>水具>折叠杯": "Sports & Entertainment > Camping & Hiking > Water Bottles",
    "家装灯饰>室内照明>夜灯": "Home & Garden > Lighting > Night Lights",
    "家居用品>厨房用品>洗菜盆>沥水篮": "Home & Garden > Kitchen,Dining & Bar > Colanders & Strainers",
    "箱包>旅行用品>收纳袋": "Luggage & Bags > Travel Accessories > Packing Organizers",
    "数码配件>手机配件>手机支架": "Consumer Electronics > Phone Accessories > Holders & Stands",
    "家用电器>厨房小电>咖啡器具": "Home Appliances > Kitchen Appliances > Coffee Makers",
    "家纺>地毯地垫>浴室垫": "Home & Garden > Home Textile > Bath Mats",
}

# 类目必填属性（简化示意，真实由 aliexpress 类目 schema 接口返回）
CATEGORY_ATTRS = {
    "Home & Garden > Kitchen,Dining & Bar > Drinkware > Vacuum Flasks": {
        "Material": "Stainless Steel",
        "Capacity": "350ml",
        "Feature": "Eco-Friendly,Stocked",
        "Drinkware Type": "Vacuum Flasks & Thermoses",
    },
    "Home & Garden > Home Storage & Organization > Desktop Storage": {
        "Material": "Acrylic",
        "Installation Type": "Standing",
        "Feature": "Eco-Friendly",
    },
    "Pet Supplies > Dog Supplies > Feeding & Watering": {
        "Material": "ABS",
        "Volume": "2L",
        "Feature": "Automatic",
    },
    "default": {
        "Material": "ABS",
        "Feature": "Eco-Friendly",
        "Origin": "Mainland China",
    },
}

# 英文标题关键词模板（模拟需求方提示词产出，真实由 prompts/ 模板 + 大模型生成）
TITLE_PARTS = {
    "家居用品>厨房吧台用品>饮具>保温杯": ("Portable Mini Vacuum Flask", "Stainless Steel Thermal Cup"),
    "家居用品>厨房用品>厨房工具>切菜器": ("Multifunctional Vegetable Slicer", "Kitchen Rotary Grater"),
    "家居用品>收纳整理>桌面收纳>收纳盒": ("Acrylic Desktop Organizer", "Drawer Type Storage Box"),
    "宠物用品>宠物喂食器>饮水器": ("Automatic Pet Water Fountain", "Ultra Quiet Circulating Dispenser"),
    "运动户外>户外装备>露营家具>折叠椅": ("Portable Folding Camping Chair", "Ultralight Aluminum Moon Chair"),
    "运动户外>户外装备>水具>折叠杯": ("Collapsible Silicone Water Cup", "Portable Travel Bottle with Lid"),
    "家装灯饰>室内照明>夜灯": ("LED Motion Sensor Night Light", "USB Rechargeable Wall Lamp"),
    "家居用品>厨房用品>洗菜盆>沥水篮": ("Stainless Steel Colander Basket", "Double Layer Vegetable Washing Bowl"),
    "箱包>旅行用品>收纳袋": ("7 Pcs Travel Packing Organizer Set", "Waterproof Luggage Storage Bags"),
    "数码配件>手机配件>手机支架": ("Aluminum Folding Phone Holder", "Desktop Live Streaming Stand"),
    "家用电器>厨房小电>咖啡器具": ("Electric Handheld Milk Frother", "USB Rechargeable Coffee Mixer"),
    "家纺>地毯地垫>浴室垫": ("Coral Fleece Non-slip Bath Mat", "Super Absorbent Bedside Rug"),
}


def candidates_by_keyword(keyword: str):
    """按关键词做简单过滤，未命中则全量返回（模拟 1688 搜索结果）。"""
    kw = (keyword or "").strip()
    if not kw:
        return list(CANDIDATES)
    hits = []
    for c in CANDIDATES:
        hay = c["title"] + c["category"] + c["supplier"]
        if any(token in hay for token in kw.split()):
            hits.append(c)
    # 家居/厨房等大类兜底
    if not hits:
        for c in CANDIDATES:
            if kw in c["title"] or kw in c["category"]:
                hits.append(c)
    return hits or list(CANDIDATES)
