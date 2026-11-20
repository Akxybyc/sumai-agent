"""内容生成器（Mock 版大模型）。

真实实现：把 prompts/aliexpress_listing_v1.md 作为 system prompt，
商品 JSON 作为 user message，调用 OpenAI 兼容接口，要求返回同结构 JSON。
此处用模板拼装产出同结构结果，保证前端与数据结构可直接切换。
"""

from __future__ import annotations

SMALL_WORDS = {"a", "an", "the", "and", "or", "for", "with", "of", "to", "in", "on", "at", "by"}


def title_case(text: str) -> str:
    words = []
    for i, w in enumerate(text.split()):
        lw = w.lower()
        if i > 0 and lw in SMALL_WORDS:
            words.append(lw)
        else:
            words.append(w[:1].upper() + w[1:].lower() if w.isupper() else w[:1].upper() + w[1:])
    return " ".join(words)


def build_title(core: str, attr: str, longtail: str, flow: str) -> str:
    """按「核心词 + 属性词 + 核心词 + 长尾词 + 流量词」拼装，控制在 115 字母内。"""
    core = title_case(core)
    attr = title_case(attr)
    longtail = title_case(longtail)
    flow = title_case(flow)
    # 第二次出现用核心词的尾部（如 Vacuum Flask），避免整段重复导致可读性差
    parts = core.split()
    core2 = " ".join(parts[-2:]) if len(parts) > 2 else core
    candidates = [
        f"{core} {attr} {core2} {longtail} {flow}",
        f"{core} {attr} {longtail} {flow}",
        f"{core} {attr} {longtail}",
    ]
    for t in candidates:
        t = "".join(ch for ch in t if ch.isalnum() or ch == " ")
        t = " ".join(t.split())
        if len(t) <= 115:
            return t
    return t[:115].rsplit(" ", 1)[0]


PACKS = {
    "饮具": {
        "attr": "Stainless Steel",
        "longtail": "Leakproof Travel Mug",
        "flow": "Office Business Gift",
        "cn_core": "不锈钢保温杯",
        "benefits": [
            ("12 小时保温保冷，冷热饮都稳", "Keeps drinks hot or cold for 12 hours"),
            ("食品级 304 不锈钢内胆，无异味", "Food grade 304 stainless steel liner"),
            ("三重密封防漏，背包里也不怕", "Triple sealed leakproof lid for bags"),
            ("仅 260g，单手握持不费力", "Lightweight 260g design fits one hand"),
            ("可定制 logo，商务送礼体面", "Custom logo available for business gifts"),
        ],
    },
    "切菜器": {
        "attr": "Multifunctional",
        "longtail": "Rotary Vegetable Grater",
        "flow": "Kitchen Accessories",
        "cn_core": "多功能切菜器",
        "benefits": [
            ("一机多用，切片切丝研磨都行", "Slice shred and grind with one tool"),
            ("滚筒设计，出菜速度提升 3 倍", "Rotary drum speeds up prep three times"),
            ("护手设计，不伤手更安心", "Hand guard keeps fingers safe"),
            ("可拆洗结构，冲水即净", "Detachable parts rinse clean fast"),
            ("加厚 ABS 机身，耐用不变形", "Thickened ABS body stays sturdy"),
        ],
    },
    "收纳": {
        "attr": "Acrylic Clear",
        "longtail": "Desktop Storage Organizer",
        "flow": "Office Bedroom Essentials",
        "cn_core": "桌面收纳盒",
        "benefits": [
            ("透明可视，找东西不用翻", "Clear design shows contents at a glance"),
            ("分层抽屉，化妆品文具分开收", "Stackable drawers separate makeup and stationery"),
            ("加厚亚克力，久用不发黄", "Thick acrylic resists yellowing"),
            ("防尘设计，减少落灰", "Dust proof design keeps items clean"),
            ("模块化组合，桌面大小都能摆", "Modular build fits any desk size"),
        ],
    },
    "宠物": {
        "attr": "Ultra Quiet",
        "longtail": "Circulating Water Dispenser",
        "flow": "Cat Dog Supplies",
        "cn_core": "宠物自动饮水机",
        "benefits": [
            ("循环过滤，水质干净宠物爱喝", "Circulating filter keeps water fresh"),
            ("静音水泵，夜间不吵人", "Quiet pump runs softly at night"),
            ("2L 大容量，出差两天不用加", "2L capacity lasts through short trips"),
            ("可拆洗结构，无死角清洁", "Detachable parts clean without blind spots"),
            ("USB 供电，摆放位置不受限", "USB powered fits anywhere"),
        ],
    },
    "折叠椅": {
        "attr": "Aluminum Alloy",
        "longtail": "Portable Camping Chair",
        "flow": "Outdoor Fishing Beach",
        "cn_core": "户外折叠椅",
        "benefits": [
            ("铝合金骨架，承重 120kg 不变形", "Aluminum frame holds up to 120kg"),
            ("3 秒展开收纳，露营说走就走", "Opens and folds in three seconds"),
            ("仅 1.2kg，背包侧袋就能装", "Only 1.2kg fits a side pocket"),
            ("加宽椅面，久坐不勒腿", "Widened seat for long sitting"),
            ("防滑脚垫，草地沙滩都稳", "Anti slip feet grip grass and sand"),
        ],
    },
    "折叠杯": {
        "attr": "Food Grade Silicone",
        "longtail": "Collapsible Travel Bottle",
        "flow": "Camping Hiking Essentials",
        "cn_core": "硅胶折叠杯",
        "benefits": [
            ("食品级硅胶，耐温 -40 到 200 度", "Food grade silicone rated -40 to 200C"),
            ("折叠后仅 3cm，口袋可装", "Folds to 3cm and fits a pocket"),
            ("密封杯盖，倒放不漏", "Sealed lid will not leak upside down"),
            ("轻至 150g，徒步无负担", "Only 150g for hiking"),
            ("易清洗，不留异味", "Easy to clean without lingering odor"),
        ],
    },
    "夜灯": {
        "attr": "Motion Sensor",
        "longtail": "USB Rechargeable Night Lamp",
        "flow": "Bedroom Hallway Stairs",
        "cn_core": "人体感应夜灯",
        "benefits": [
            ("人体感应，起夜自动亮", "Motion sensor lights up automatically"),
            ("暖光不刺眼，不扰睡眠", "Warm glow is gentle on eyes"),
            ("USB 充电，一次用一个月", "USB charge lasts about a month"),
            ("磁吸安装，随处可贴", "Magnetic mount installs anywhere"),
            ("低功耗设计，全年省电", "Low power design saves energy"),
        ],
    },
    "沥水": {
        "attr": "Stainless Steel",
        "longtail": "Double Layer Washing Basket",
        "flow": "Kitchen Vegetable Fruit",
        "cn_core": "不锈钢沥水篮",
        "benefits": [
            ("双层设计，洗沥一步完成", "Two layers wash and drain in one step"),
            ("加厚不锈钢，承重不变形", "Thickened steel holds heavy loads"),
            ("细密滤孔，小颗粒也不漏", "Fine holes keep small items in"),
            ("防锈易洗，用完冲一下", "Rust proof and rinses clean"),
            ("可叠放收纳，不占橱柜", "Stackable to save cabinet space"),
        ],
    },
    "收纳袋": {
        "attr": "Waterproof",
        "longtail": "Travel Packing Organizer Set",
        "flow": "Luggage Suitcase Essentials",
        "cn_core": "旅行收纳袋七件套",
        "benefits": [
            ("七件套分类，行李一开就找到", "Seven pieces keep luggage organized"),
            ("防水面料，洗漱用品不怕漏", "Waterproof fabric protects toiletries"),
            ("压缩设计，多装三成衣物", "Compression design fits 30 percent more"),
            ("轻量网面，透气不闷味", "Lightweight mesh keeps clothes fresh"),
            ("适配 20 到 28 寸行李箱", "Fits 20 to 28 inch suitcases"),
        ],
    },
    "支架": {
        "attr": "Aluminum Alloy",
        "longtail": "Foldable Desk Phone Stand",
        "flow": "Live Streaming Office",
        "cn_core": "铝合金手机支架",
        "benefits": [
            ("铝合金机身，稳不晃", "Aluminum body stays steady"),
            ("多角度调节，追剧直播都合适", "Adjustable angles for video and live streaming"),
            ("折叠后巴掌大，随身带", "Folds to palm size for travel"),
            ("硅胶垫防滑，不刮手机", "Silicone pads protect your phone"),
            ("兼容 4 到 12 寸设备", "Fits devices from 4 to 12 inches"),
        ],
    },
    "咖啡": {
        "attr": "USB Rechargeable",
        "longtail": "Handheld Milk Frother",
        "flow": "Home Cafe Kitchen",
        "cn_core": "电动咖啡打泡器",
        "benefits": [
            ("15 秒打出绵密奶泡", "Creates dense foam in 15 seconds"),
            ("USB 充电，无线使用", "USB rechargeable and cordless"),
            ("低噪电机，清晨不吵人", "Quiet motor for early mornings"),
            ("可拆打泡头，冲洗即净", "Detachable whisk rinses clean"),
            ("小巧机身，出差也能带", "Compact body travels well"),
        ],
    },
    "地垫": {
        "attr": "Coral Fleece",
        "longtail": "Non Slip Absorbent Bath Mat",
        "flow": "Bedroom Bathroom Decor",
        "cn_core": "珊瑚绒浴室地垫",
        "benefits": [
            ("珊瑚绒面料，踩上去软", "Coral fleece feels soft underfoot"),
            ("瞬吸水分，出浴不湿脚", "Absorbs water fast after shower"),
            ("防滑底背，湿地也不滑", "Non slip backing grips wet floors"),
            ("可机洗，打理省心", "Machine washable for easy care"),
            ("不掉毛不掉色，久用如新", "No shedding or fading over time"),
        ],
    },
}

DEFAULT_PACK = {
    "attr": "Multifunctional",
    "longtail": "Portable Home Essential",
    "flow": "Daily Use Gift",
    "cn_core": "家居用品",
    "benefits": [
        ("用料扎实，日常使用耐用", "Sturdy build for daily use"),
        ("设计紧凑，收纳不占地", "Compact design saves space"),
        ("细节打磨，手感顺滑", "Smooth finish with careful details"),
        ("易清洁，维护省心", "Easy to clean and maintain"),
        ("多场景适用，实用性强", "Works across multiple scenarios"),
    ],
}


KEYWORD_EN = {
    "保温杯": "Vacuum Flask", "水杯": "Water Bottle", "杯子": "Drink Cup",
    "收纳盒": "Storage Box", "收纳": "Storage Organizer",
    "宠物": "Pet Supplies", "猫": "Cat Supplies", "狗": "Dog Supplies",
    "折叠椅": "Camping Chair", "露营": "Camping Gear", "户外": "Outdoor Gear",
    "折叠杯": "Collapsible Cup", "夜灯": "Motion Sensor Night Light",
    "沥水": "Drain Basket", "收纳袋": "Packing Organizer",
    "支架": "Phone Stand", "咖啡": "Milk Frother", "地垫": "Bath Mat",
}


def guess_core_en(category_cn: str) -> str:
    for key, en in KEYWORD_EN.items():
        if key in category_cn:
            return en
    return ""


ATTR_ZH = {
    "Stainless Steel": "不锈钢",
    "Acrylic Clear": "亚克力透明",
    "Multifunctional": "多功能",
    "Ultra Quiet": "超静音",
    "Aluminum Alloy": "铝合金",
    "Food Grade Silicone": "食品级硅胶",
    "Motion Sensor": "人体感应",
    "Waterproof": "防水",
    "USB Rechargeable": "USB充电",
    "Coral Fleece": "珊瑚绒",
}


def pick_pack(category_cn: str) -> dict:
    aliases = {
        "保温杯": "饮具", "水杯": "饮具", "杯子": "饮具", "杯": "饮具",
        "收纳": "收纳", "置物": "收纳",
        "宠物": "宠物", "猫": "宠物", "狗": "宠物",
        "露营": "折叠椅", "户外": "折叠椅", "椅子": "折叠椅",
        "折叠杯": "折叠杯", "夜灯": "夜灯", "台灯": "夜灯",
        "沥水": "沥水", "收纳袋": "收纳袋", "行李箱": "收纳袋",
        "支架": "支架", "咖啡": "咖啡", "地垫": "地垫",
    }
    for key, pack_key in aliases.items():
        if key in category_cn and pack_key in PACKS:
            return PACKS[pack_key]
    for key, pack in PACKS.items():
        if key in category_cn:
            return pack
    return DEFAULT_PACK


def build_content(item: dict, title_en: str, core_en: str, cat_en: str, attrs: dict) -> dict:
    pack = pick_pack(item["category"])
    core_cn = pack["cn_core"]
    attr_zh = ATTR_ZH.get(pack["attr"], "")
    cn_title = f"{core_cn} {'' if attr_zh and attr_zh in core_cn else attr_zh} {item['skus'][0]}款 跨境热销"
    cn_title = " ".join(cn_title.split())

    descriptions = [
        {
            "style": "活泼吸睛",
            "zh": f"✨ {core_cn}来啦！{pack['benefits'][0][0]}，{pack['benefits'][1][0]}。"
                  f"小体积大用处，租房、宿舍、办公室都能放，日常用一次就回不去～",
            "en": f"✨ Meet your new favorite {core_en.lower()}! {pack['benefits'][0][1]} and {pack['benefits'][1][1]}. "
                  f"Compact enough for dorms and offices, useful enough for every day.",
        },
        {
            "style": "简约专业",
            "zh": f"{core_cn}，采用{attrs.get('Material', '优质材料')}材质。{pack['benefits'][0][0]}；"
                  f"{pack['benefits'][2][0]}。结构简洁，适合家庭与商用场景。",
            "en": f"{core_en}, made with {attrs.get('Material', 'premium material')}. "
                  f"{pack['benefits'][0][1]}. {pack['benefits'][2][1]}. A clean design for home and commercial use.",
        },
        {
            "style": "场景种草",
            "zh": f"周末的清晨，桌上放着{core_cn}。{pack['benefits'][1][0]}，{pack['benefits'][3][0]}。"
                  f"不用刻意打理，生活自然就顺了一点。",
            "en": f"A slow weekend morning with the {core_en.lower()} within reach. "
                  f"{pack['benefits'][1][1]}. {pack['benefits'][3][1]}. Small upgrades, calmer days.",
        },
    ]

    bullets = [{"zh": zh, "en": en} for zh, en in pack["benefits"]]

    images = [
        {"no": 1, "type": "首图", "zh": "白底正面图，产品占画面 80%，右上角放 3 个核心卖点图标",
         "en": "Main image on white, product fills 80%, three key benefit icons top right"},
        {"no": 2, "type": "细节图", "zh": "特写材质与做工，标注关键尺寸（cm / inch）",
         "en": "Close up of material and build, key dimensions in cm and inch"},
        {"no": 3, "type": "场景图", "zh": "欧美家庭真实使用场景，人物自然入镜",
         "en": "Real Western home scene with a person using the product"},
        {"no": 4, "type": "场景图", "zh": "户外 / 办公第二场景，体现便携与多用途",
         "en": "Second scene outdoors or in office showing portability"},
        {"no": 5, "type": "功能演示图", "zh": "分步骤演示核心功能，3 格构图，配简短英文标注",
         "en": "Three panel demo of the core function with short English labels"},
        {"no": 6, "type": "参数信息图", "zh": "尺寸、重量、材质、包装清单，cm 与 inch 双单位",
         "en": "Size, weight, material and package list in both cm and inch"},
    ]

    words = [w for w in title_en.split() if len(w) > 2]
    search_terms = {
        "title_words": words[:8],
        "backend": [
            core_en.lower(), f"{core_en.lower()} for home", f"portable {core_en.lower()}",
            f"{core_en.lower()} gift", f"travel {core_en.lower()}", f"{core_en.lower()} wholesale",
        ],
    }

    compliance = [
        "侵权风险：标题与图片不得出现 Apple / Samsung / Disney 等品牌词与卡通形象，禁用 Best / No.1 等绝对化用语。",
        f"目标受众：欧美 25-45 岁家庭用户，注重实用与性价比，客单价建议控制在 8-25 美元区间。",
        "短描述截取：优先取第 1、2、5 条 Bullet，前 60 个英文单词内讲清材质、核心功能与适用场景。",
        "类目资质：提报前确认所属类目无强制认证要求；涉及电器需核对电压与插头标准。",
    ]

    attr_pairs = {
        "Material": ("材质", "Material"),
        "Capacity": ("容量", "Capacity"),
        "Feature": ("特性", "Feature"),
        "Brand Name": ("品牌", "Brand Name"),
        "Origin": ("产地", "Origin"),
    }
    attr_value_zh = {
        "Stainless Steel": "不锈钢", "Acrylic": "亚克力", "ABS": "ABS 工程塑料",
        "No Brand": "无品牌", "Mainland China": "中国大陆",
    }
    attr_list = []
    for k, v in attrs.items():
        zh_name, en_name = attr_pairs.get(k, (k, k))
        attr_list.append({
            "name_zh": zh_name,
            "name_en": en_name,
            "value_zh": attr_value_zh.get(v, v),
            "value_en": v,
        })
    attr_list.append({"name_zh": "货号", "name_en": "Model Number", "value_zh": item["id"].split("-")[-1], "value_en": item["id"].split("-")[-1]})

    return {
        "prompt_version": "速卖通欧美站全套上架方案 v1",
        "title": {"en": title_en, "cn": cn_title, "letters": len(title_en)},
        "descriptions": descriptions,
        "bullets": bullets,
        "images": images,
        "search_terms": search_terms,
        "compliance": compliance,
        "attrs": attr_list,
    }

# ============ 标题：按「115 个英文字母」硬约束生成 ============
SMALL_WORDS = {"a", "an", "the", "and", "or", "for", "with", "of", "in", "on", "at", "to", "by", "from"}


def _title_case(text: str) -> str:
    out = []
    for i, w in enumerate(text.split()):
        lw = w.lower()
        if i > 0 and lw in SMALL_WORDS:
            out.append(lw)
        elif w.isupper() and len(w) >= 2:      # BBQ / USB / LED 保持大写
            out.append(w)
        else:
            out.append(lw[:1].upper() + lw[1:] if lw else lw)
    return " ".join(out)


def _letters(t: str) -> int:
    return sum(1 for ch in t if ch.isalpha())


def validate_title(t: str, core: str) -> dict:
    letters = _letters(t)
    words = t.split()
    core_words = core.lower().split()
    core_pos = 0
    if core_words:
        low = t.lower()
        core_pos = low.find(" ".join(core_words))
    repeat = t.lower().count(core_words[0]) if core_words else 0
    bad_case = [w for w in words if w.lower() not in SMALL_WORDS and w[:1].islower()]
    return {
        "letters": letters,
        "chars": len(t),
        "core_pos": core_pos,
        "core_repeat": repeat,
        "punct_free": not any(not (c.isalnum() or c == " ") for c in t),
        "case_ok": not bad_case,
        "letters_ok": letters == 115,
        "ok": letters == 115 and core_pos < 30 and repeat <= 3
              and not any(not (c.isalnum() or c == " ") for c in t) and not bad_case,
    }


def build_title_v2(core: str, attr: str, longtail: str, flow: str,
                   filler: list[str] | None = None, target: int = 115,
                   seed: str = "") -> tuple[str, dict]:
    """核心+属性+核心+长尾+流量，实词大写，无标点，精准 target 个英文字母。"""
    import itertools

    core_t = _title_case(core)
    cw = core_t.split()
    core2 = " ".join(cw[-2:]) if len(cw) > 2 else core_t
    core_low = {w.lower() for w in cw}

    def _strip_core(text: str) -> str:
        """修饰词里不许再出现核心词，保证核心词最多出现 2 次。"""
        kept = [w for w in text.split() if w.lower() not in core_low]
        return " ".join(kept)

    base = f"{core_t} {_title_case(_strip_core(attr))} {core2} {_title_case(_strip_core(longtail))} {_title_case(_strip_core(flow))}"
    base = "".join(ch for ch in base if ch.isalnum() or ch == " ")
    base = " ".join(base.split())

    POOL = [w for w in (filler or []) if w and w.isalpha()]
    POOL += ["Home", "Use", "Kit", "Pro", "Set", "New", "Hot", "Gift", "Easy", "Durable",
             "Daily", "Clean", "Multi", "Travel", "Office", "Compact", "Outdoor", "Premium",
             "Portable", "Lightweight", "Insulated", "Reusable", "Ecofriendly", "Gadget",
             "Organizer", "Holder", "Stand", "Box", "Bag", "Rack", "Shelf", "Cup", "Mug"]
    POOL = [w for w in dict.fromkeys(POOL) if w.isalpha()]


    need = target - _letters(base)
    t = base

    def add_words(need_n: int, used_text: str):
        """从词库找 1~3 个词，字母数之和恰好等于 need_n。"""
        avail = [w for w in POOL if w.lower() not in used_text.lower()]
        for k in (1, 2, 3):
            best = None
            for combo in itertools.combinations(avail, k):
                if sum(len(w) for w in combo) == need_n:
                    best = combo
                    break
            if best:
                return list(best)
        return []

    if need > 0:
        words = add_words(need, t)
        if words:
            t = f"{t} {' '.join(words)}"
        else:
            # 尽力接近：先补到不超过 target，再找单字替换
            for w in POOL:
                if _letters(t) + len(w) <= target and w.lower() not in t.lower():
                    t = f"{t} {w}"
            rest = target - _letters(t)
            if rest > 0:
                for w in POOL:
                    gap = rest - len(w)
                    if 0 <= gap <= 3 and w.lower() not in t.lower():
                        t = f"{t} {w}"
                        break
    elif need < 0:
        words = t.split()
        while _letters(t) > target and len(words) > 6:
            words.pop()
            t = " ".join(words)
        rest = target - _letters(t)
        if rest > 0:
            ws = add_words(rest, t)
            if ws:
                t = f"{t} {' '.join(ws)}"

    # 最后 1 个字母的微调：替换末尾补充词
    for _ in range(6):
        diff = target - _letters(t)
        if diff == 0:
            break
        words = t.split()
        if len(words) < 7:
            break
        tail = words[-1]
        cand = next((w for w in POOL
                     if len(w) == len(tail) + diff and w.lower() not in t.lower()), None)
        if not cand:
            cand = next((w for w in POOL
                         if len(w) == len(tail) and w.lower() not in t.lower()
                         and abs(_letters(" ".join(words[:-1] + [w])) - target) < abs(diff)), None)
        if not cand:
            break
        words[-1] = cand
        t = " ".join(words)

    # 同长度替换尾部词，制造差异且不改变字母总数
    if seed:
        import hashlib as _hl
        h = int(_hl.md5(seed.encode("utf-8")).hexdigest()[:8], 16)
        words = t.split()
        used = {w.lower() for w in words}
        cands = [w for w in POOL if w.lower() not in used]
        reps = 0
        for idx in range(len(words) - 1, max(len(words) - 6, 5), -1):
            if reps >= 2:
                break
            cur = words[idx]
            same = next((w for w in cands if len(w) == len(cur)), None)
            if same:
                words[idx] = same
                cands.remove(same)
                reps += 1
        t = " ".join(words)

    # 结尾不能是虚词（of / for / with / and …）
    _w = t.split()
    while len(_w) > 3 and _w[-1].lower() in SMALL_WORDS:
        _w.pop()
        t = " ".join(_w)

    # 去掉零散的 1~2 字母残词（如 G / AB），保持可读
    t = " ".join(w for w in t.split() if len(w) >= 3 or w.isdigit())
    t = "".join(ch for ch in t if ch.isalnum() or ch == " ")
    t = " ".join(t.split())
    return t, validate_title(t, core_t)

# ============ 从商品标题识别核心词（长词优先） ============
TITLE_CORE = {
    # 厨房
    "擦丝器": "Vegetable Slicer", "刨丝器": "Vegetable Slicer", "切菜神器": "Vegetable Chopper",
    "切菜器": "Vegetable Chopper", "土豆丝": "Potato Shredder", "削皮刀": "Peeler",
    "剪刀": "Kitchen Scissors", "烤肉夹": "BBQ Tongs", "食物夹": "Kitchen Tongs",
    "电子秤": "Kitchen Scale", "厨房秤": "Kitchen Scale", "计时器": "Kitchen Timer",
    "调味盒": "Spice Box", "调料盒": "Spice Box", "调料瓶": "Spice Jar", "油壶": "Oil Dispenser",
    "置物架": "Kitchen Shelf", "沥水架": "Dish Rack", "刀架": "Knife Block",
    "砧板": "Cutting Board", "菜板": "Cutting Board", "锅铲": "Spatula", "打蛋器": "Whisk",
    "保鲜盒": "Food Container", "密封罐": "Sealed Jar", "收纳筐": "Storage Basket",
    "垃圾袋": "Trash Bag", "洗碗": "Dishwashing Tool", "钢丝球": "Scouring Pad",
    "烘焙": "Baking Tool", "模具": "Baking Mold", "手套": "Silicone Gloves",
    # 家居
    "收纳盒": "Storage Box", "收纳箱": "Storage Bin", "衣柜": "Wardrobe Organizer",
    "衣架": "Clothes Hanger", "挂钩": "Wall Hook", "置物": "Storage Rack",
    "垃圾桶": "Trash Can", "拖把": "Mop", "扫把": "Broom", "除尘": "Cleaning Brush",
    "抹布": "Cleaning Cloth", "喷壶": "Spray Bottle", "桌面": "Desktop Organizer",
    # 宠物
    "饮水机": "Pet Water Fountain", "喂食器": "Pet Feeder", "猫砂": "Cat Litter",
    "宠物垫": "Pet Mat", "牵引绳": "Pet Leash", "猫爬架": "Cat Tree", "狗窝": "Dog Bed",
    "磨牙": "Pet Chew Toy", "火腿肠": "Pet Snack", "木屑": "Pet Bedding",
    # 3C / 配件
    "手机支架": "Phone Holder", "车载支架": "Car Phone Holder", "数据线": "USB Cable",
    "充电器": "Charger", "耳机": "Earphones", "鼠标垫": "Mouse Pad", "键盘": "Keyboard",
    "保温杯": "Vacuum Flask", "水杯": "Water Bottle",
}


def core_from_item(title_cn: str, category_cn: str = "") -> str:
    """优先从标题里识别具体品类词，其次按类目兜底。"""
    text = title_cn or ""
    for key in sorted(TITLE_CORE, key=len, reverse=True):
        if key in text:
            return TITLE_CORE[key]
    hit = guess_core_en(category_cn) or guess_core_en(text)
    if hit and hit != "Multifunctional Household Item":
        return hit
    # 最后兜底：按大类给一个中性但可用的词
    for k, v in (("厨房", "Kitchen Tool"), ("宠物", "Pet Supplies"),
                 ("收纳", "Storage Organizer"), ("户外", "Outdoor Gear")):
        if k in (category_cn + text):
            return v
    return "Household Item"
