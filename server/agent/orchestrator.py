"""智能体编排：意图识别 → 任务规划 → 工具调用 → 人工断点。

当前为 mock 实现（工具返回假数据），编排结构与后续 LangGraph 图一一对应：
节点 = start → plan → call_tool → human_gate → call_tool → report
"""

from __future__ import annotations

import asyncio
import json
import random
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from content import (build_content, build_title, build_title_v2, core_from_item,
                     guess_core_en, pick_pack)
from mock.data import CATEGORY_ATTRS, CATEGORY_MAP, TITLE_PARTS, candidates_by_keyword


def now_str() -> str:
    return datetime.now().strftime("%H:%M:%S")


@dataclass
class Draft:
    id: str
    source_id: str
    title_cn: str
    title_en: str
    category_cn: str
    category_en: str
    attrs: dict
    cost_cny: float          # 1688 采购成本
    supply_price: float      # 全托管供货价（CNY）
    weight_g: int
    stock: int
    warehouse: str
    lead_days: int
    skus: list
    icon: str
    hue: int
    content: dict = field(default_factory=dict)
    status: str = "pending"  # pending | approved | submitted | on_sale
    sku_code: str = ""       # 货品/SKU 编码
    sku_prefix: str = ""     # 批量填充用前缀
    product_id: str = ""
    error: str = ""
    source_url: str = ""   # 1688 商品链接，推送到 ERP 时用
    qualification: dict = field(default_factory=dict)  # 资质要求：{required, items:[{name,note}]}
    qual_status: str = "none"   # none | pending | approved | rejected
    qual_cert: dict = field(default_factory=dict)  # {cert_no, expire, operator, at}
    images: list = field(default_factory=list)     # 1688 主图/附图 URL
    ms_detail_id: int = 0    # 妙手公共采集箱 detailId（0=未入库）
    freight_cny: float = 0.0        # 国内运费（1688→集运仓）
    price_rule: str = ""            # 供货价计算公式说明
    need_manual_price: bool = False  # 成本 <10 元，需客户自己定价


@dataclass
class Task:
    id: str
    name: str
    kind: str  # generate | publish
    status: str = "running"  # running | done | failed | waiting_human
    progress: int = 0
    step: str = ""
    total: int = 0
    done_count: int = 0
    failed_count: int = 0
    created_at: str = field(default_factory=now_str)
    detail: list = field(default_factory=list)


class AgentState:
    STORE = Path(__file__).resolve().parents[2] / "data" / "drafts.json"

    def __init__(self) -> None:
        self.drafts: dict[str, Draft] = {}
        self.tasks: dict[str, Task] = {}
        self.jobs: dict[str, dict] = {}
        self.selected: list[str] = []
        self.logs: list[dict] = []
        self.seq = 0
        self.usage = {"calls": 0, "prompt_chars": 0, "completion_chars": 0}
        self.load()

    # ---------- 持久化 ----------
    def persist(self) -> None:
        try:
            self.STORE.parent.mkdir(parents=True, exist_ok=True)
            data = [asdict(d) for d in self.drafts.values()]
            self.STORE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    def load(self) -> None:
        try:
            if not self.STORE.exists():
                return
            raw = json.loads(self.STORE.read_text(encoding="utf-8"))
            for d in raw:
                try:
                    draft = Draft(**d)
                    self.drafts[draft.id] = draft
                except Exception:
                    continue
        except Exception:
            pass

    # ---------- 工具方法 ----------
    def next_seq(self) -> int:
        self.seq += 1
        return self.seq

    LOG_FILE = Path(__file__).resolve().parents[2] / "data" / "agent.log"

    def add_log(self, role: str, text: str, extra: dict | None = None) -> dict:
        item = {"role": role, "text": text, "time": now_str(), **(extra or {})}
        self.logs.append(item)
        try:
            with open(self.LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return item

    # ---------- 资质风控 ----------
    QUAL_RULES = [
        (["保温", "水杯", "杯子", "餐具", "饭盒", "锅", "厨房", "饮水"],
         "食品接触材料检测报告", "与食品接触，需 GB 4806 / LFGB / FDA 检测报告"),
        (["充电", "电池", "电源", "电动", "锂电", "灯"],
         "3C / CE / UN38.3", "含电或电池，需 3C（国内）与 CE/UN38.3（跨境）"),
        (["儿童", "玩具", "婴儿", "宝宝"],
         "CPC / EN71", "儿童用品需 CPC（美国）或 EN71（欧盟）"),
        (["化妆", "护肤", "面膜", "口红", "精油"],
         "化妆品备案 / CPNP", "需备案凭证或 CPNP 通报"),
        (["医疗", "口罩", "体温计", "血压"],
         "医疗器械备案", "需医疗器械备案凭证"),
    ]

    def check_qualification(self, text: str) -> dict:
        hits = []
        for kws, name, note in self.QUAL_RULES:
            if any(k in text for k in kws):
                hits.append({"name": name, "note": note})
        return {"required": bool(hits), "items": hits}

    # ---------- 选品策略 ----------
    CATEGORY_ALIASES = {
        "厨房": ["厨房", "饮具", "切菜", "沥水", "咖啡"],
        "家居": ["家居", "收纳", "家纺", "地垫"],
        "宠物": ["宠物", "猫", "狗"],
        "户外": ["户外", "露营", "折叠"],
        "数码": ["数码", "手机", "支架", "灯"],
    }

    def detect_category(self, text: str) -> str:
        for cat, keys in self.CATEGORY_ALIASES.items():
            if any(k in text for k in keys):
                return cat
        return ""

    def auto_pick(self, text: str, count: int = 3, min_sales: int = 3000,
                  price_min: float = 5, price_max: float = 150) -> list[dict]:
        """按策略打分自动选品（mock 已移除，请走真实采集）。"""
        raise RuntimeError("已移除 mock 选品：请走 /api/1688/auto 真实采集")
        cat = self.detect_category(text)
        pool = [c for c in candidates_by_keyword("") if not cat or cat in c["category"] or any(
            k in c["category"] for k in self.CATEGORY_ALIASES.get(cat, []))]
        pool = [c for c in pool if c["sales_30d"] >= min_sales and price_min <= c["price_cny"] <= price_max]
        if not pool:
            pool = candidates_by_keyword("")

        max_sales = max(c["sales_30d"] for c in pool) or 1
        max_coll = max(c["collectors"] for c in pool) or 1
        scored = []
        for c in pool:
            s_sales = c["sales_30d"] / max_sales
            s_coll = c["collectors"] / max_coll
            s_rating = (c["rating"] - 4.5) / 0.5 if c["rating"] > 4.5 else 0
            s_price = 1 - abs(c["price_cny"] - 30) / 120  # 偏好 20~45 元价格带
            score = round((s_sales * 0.4 + s_coll * 0.3 + s_rating * 0.2 + s_price * 0.1) * 100, 1)
            scored.append({**c, "score": score,
                           "reason": f"30天销量 {c['sales_30d']:,} · 采集 {c['collectors']:,} · {c['rating']}分"})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:count]

    # ---------- 意图识别 ----------
    def route(self, text: str) -> str:
        t = text.lower()
        if any(k in t for k in ["自动选品", "一条龙", "选品并上架", "选品上架", "直接上架", "自动上架", "帮我选品上架"]):
            return "auto"
        if "真实" in t and any(k in t for k in ["选品", "采集", "数据", "跑"]):
            return "real"
        if any(k in t for k in ["上架", "发布", "上传", "刊登", "提报"]):
            return "publish"
        if any(k in t for k in ["选品", "找货", "找产品", "新品", "爆款", "搜索", "采集",
                                "推荐", "好卖", "不需要资质", "免资质", "无需资质"]):
            return "select"
        if any(k in t for k in ["任务", "进度", "状态", "多少"]):
            return "status"
        return "chat"

    # ---------- 选品 ----------
    def search(self, text: str) -> list[dict]:
        stop = ["选品", "找货", "找产品", "帮我", "给我", "上架", "发布", "采集", "搜索", "一下", "产品", "商品", "新品", "爆款"]
        kw = text
        for s in stop:
            kw = kw.replace(s, " ")
        # 提取类目关键词
        tokens = [x for x in kw.replace("，", " ").replace(",", " ").split() if len(x) >= 2]
        keyword = tokens[0] if tokens else ""
        raise RuntimeError("已移除 mock 选品：请调用 /api/1688/auto 走真实 1688 采集")

    # ---------- 生成草稿 ----------
    async def generate_job(self, job_id: str, ids: list[str]) -> None:
        raise RuntimeError("已移除 mock 生成任务：草稿统一由真实采集流程创建")
        job = self.jobs[job_id]
        task = self.tasks[job["task_id"]]
        picks = [c for c in candidates_by_keyword("") if c["id"] in ids]
        task.total = len(picks)
        job["total"] = len(picks)

        steps = [
            ("采集 1688 商品详情（标题 / 主图 / SKU / 属性）", 0.25),
            ("加载提示词模板（全套上架方案），调用大模型生成内容", 0.85),
            ("匹配速卖通半托管类目与必填属性", 0.55),
            ("写入商品草稿", 0.35),
        ]

        for idx, item in enumerate(picks, start=1):
            base = (idx - 1) / len(picks) * 100
            for step_idx, (label, delay) in enumerate(steps, start=1):
                task.step = f"{label} · {idx}/{len(picks)}"
                job["step"] = task.step
                await asyncio.sleep(delay * random.uniform(0.5, 1.0))
                task.progress = int(base + step_idx / len(steps) * (100 / len(picks)))
                job["progress"] = task.progress

            draft = self.build_draft(item, idx)
            self.drafts[draft.id] = draft
            self.usage["calls"] += 1
            self.usage["prompt_chars"] += 1800 + len(item["title"]) * 2
            self.usage["completion_chars"] += 1400
            task.done_count += 1
            task.detail.append({"id": draft.id, "title": draft.title_en, "status": "draft"})

        task.progress = 100
        task.status = "done"
        task.step = f"已生成 {len(picks)} 个草稿，等待人工审核"
        job["status"] = "done"
        job["progress"] = 100
        job["step"] = task.step
        job["draft_ids"] = [d.id for d in self.drafts.values() if d.source_id in ids]

    def build_draft(self, item: dict, idx: int) -> Draft:
        raise RuntimeError("已移除 mock 草稿：请用 build_draft_from_source（真实 1688 数据）")
        self.next_seq()
        cat_en = CATEGORY_MAP.get(item["category"], "Home & Garden > Home Storage & Organization")
        title_a, title_b = TITLE_PARTS.get(item["category"], ("Multifunctional Household Item", "Portable Convenient Design"))
        pack = pick_pack(item["category"])
        title_en = build_title(title_a, pack["attr"], pack["longtail"], pack["flow"])
        supply_price = round(item["price_cny"] * 1.35, 2)  # 供货价 = 采购成本 × 1.35
        attrs = dict(CATEGORY_ATTRS.get(cat_en, CATEGORY_ATTRS["default"]))
        attrs["Brand Name"] = "No Brand"
        attrs["Origin"] = "Mainland China"
        prefix = f"ZNZ{datetime.now():%y%m}{idx:02d}"
        content = build_content(item, title_en, title_a, cat_en, attrs)
        return Draft(
            id=f"draft-{int(time.time() * 1000)}-{idx}",
            source_id=item["id"],
            title_cn=item["title"],
            title_en=title_en[:180],
            category_cn=item["category"],
            category_en=cat_en,
            attrs=attrs,
            cost_cny=item["price_cny"],
            supply_price=supply_price,
            weight_g=item["weight_g"],
            stock=1000,
            warehouse="国内仓（义乌）",
            lead_days=3,
            skus=item["skus"],
            icon=item["icon"],
            hue=item["hue"],
            content=content,
            sku_code=f"{prefix}-01",
            sku_prefix=prefix,
        )

    # ---------- 提报 ----------
    async def publish_job(self, job_id: str, draft_ids: list[str]) -> None:
        job = self.jobs[job_id]
        task = self.tasks[job["task_id"]]
        drafts = [self.drafts[i] for i in draft_ids if i in self.drafts]
        task.total = len(drafts)
        job["total"] = len(drafts)

        # 资质闸门：需资质但未登记的，直接跳过
        allowed, blocked = [], []
        for d in drafts:
            if d.qualification.get("required") and d.qual_status != "approved":
                blocked.append(d)
            else:
                allowed.append(d)
        for b in blocked:
            task.detail.append({"id": b.id, "title": b.title_en, "status": "blocked",
                                "reason": "需资质未登记，已跳过"})
        task.step = f"资质闸门：通过 {len(allowed)} / 拦截 {len(blocked)}"
        job["step"] = task.step
        await asyncio.sleep(0.4)

        for i, d in enumerate(allowed, start=1):
            task.step = f"RPA 填写「发布商品」表单 · {i}/{max(len(allowed),1)}"
            job["step"] = task.step
            await asyncio.sleep(random.uniform(0.6, 1.1))
            task.step = f"上传主图与附图，匹配类目属性 · {i}/{max(len(allowed),1)}"
            job["step"] = task.step
            await asyncio.sleep(random.uniform(0.5, 0.9))
            task.step = f"保存草稿并提交审核 · {i}/{max(len(allowed),1)}"
            job["step"] = task.step
            await asyncio.sleep(random.uniform(0.5, 0.9))
            d.status = "on_sale" if i % 5 else "submitted"
            d.product_id = f"10050{random.randint(10000000, 99999999)}"
            task.done_count += 1
            task.detail.append({"id": d.id, "title": d.title_en, "status": d.status, "pid": d.product_id})
            task.progress = int(i / max(len(allowed),1) * 100)
            job["progress"] = task.progress

        task.progress = 100
        task.status = "done"
        task.step = f"提报完成：{task.done_count} 个已提交平台审核，拦截 {len(blocked)} 个"
        job["status"] = "done"
        job["progress"] = 100
        job["step"] = task.step
        self.persist()

    # ---------- 真实数据选品 ----------
    def score_real(self, items: list[dict], count: int = 3,
                   price_min: float = 3, price_max: float = 150) -> list[dict]:
        pool = [i for i in items if price_min <= i.get("price_cny", 0) <= price_max and i.get("sales_30d", 0) >= 300]
        if not pool:
            pool = items
        max_sales = max((i.get("sales_30d", 0) for i in pool), default=1) or 1
        max_rep = max((i.get("repurchase_rate", 0) for i in pool), default=1) or 1
        scored = []
        for i in pool:
            s_sales = i.get("sales_30d", 0) / max_sales
            s_rep = i.get("repurchase_rate", 0) / max_rep
            s_price = 1 - min(abs(i.get("price_cny", 0) - 22) / 100, 1)  # 偏好 12~30 元
            s_supplier = 1.0 if i.get("supplier") else 0.4
            score = round((s_sales * 0.4 + s_rep * 0.3 + s_price * 0.2 + s_supplier * 0.1) * 100, 1)
            parts = [f"30天销量 {i.get('sales_30d', 0):,}"]
            if i.get("repurchase_rate"):
                parts.append(f"回头率 {i['repurchase_rate']}%")
            if i.get("supplier"):
                parts.append(i["supplier"][:14])
            qual = self.check_qualification(f"{i.get('category', '')} {i.get('title', '')}")
            if qual["required"]:
                parts.append("需资质")
            scored.append({**i, "score": score, "reason": " · ".join(parts), "qualification": qual})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:count]

    def build_draft_from_source(self, item: dict, idx: int) -> Draft:
        """用真实 1688 商品（已补详情）生成草稿。"""
        cat_cn = item.get("category") or "家居"
        pack = pick_pack(cat_cn)
        core_en = core_from_item(item.get("title", ""), cat_cn) or "Household Item"
        # 用速卖通真实爆款词替换模板词（拿不到就退回模板）
        attr_w, longtail_w, flow_w = pack["attr"], pack["longtail"], pack["flow"]
        trend_info = {}
        try:
            from agent import trend_words
            tw = trend_words.extract(core_en)
            if tw.get("ok") and tw.get("attr"):
                attr_w = tw["attr"] or attr_w
                longtail_w = tw["longtail"] or longtail_w
                flow_w = tw["flow"] or flow_w
                trend_info = {"fetched_at": tw.get("fetched_at"), "sample": tw.get("count"),
                              "top_words": (tw.get("top_words") or [])[:12],
                              "source": "aliexpress_hot"}
        except Exception as e:  # noqa: BLE001
            trend_info = {"error": f"{type(e).__name__}: {e}"}

        title_en, title_check = build_title_v2(core_en, attr_w, longtail_w, flow_w,
                                              seed=item.get("id") or item.get("title", ""))
        cat_en = CATEGORY_MAP.get(cat_cn, "Home & Garden > Home Storage & Organization")
        from agent.attrs_en import translate as _attrs_en

        attrs = dict(CATEGORY_ATTRS.get(cat_en, CATEGORY_ATTRS["default"]))
        attrs.update(_attrs_en(item.get("attributes") or {}))
        attrs.setdefault("Brand Name", "No Brand")
        attrs.setdefault("Origin", "Mainland China")
        cost = float(item.get("price_cny") or 0)
        prefix = f"ZNZ{datetime.now():%y%m}{idx:02d}"
        content = build_content(item, title_en, core_en, cat_en, attrs)
        content["title_check"] = title_check
        content["trend_source"] = trend_info
        from agent import pricing as _pricing_mod

        _pricing = _pricing_mod.calc(cost, float(item.get("freight_cny") or 0))
        qual = self.check_qualification(f"{cat_cn} {item.get('title', '')}")
        return Draft(
            id=f"draft-{int(time.time() * 1000)}-{idx}",
            source_id=item.get("id", ""),
            title_cn=item.get("title", ""),
            title_en=title_en[:180],
            category_cn=cat_cn,
            category_en=cat_en,
            attrs=attrs,
            cost_cny=cost,
            supply_price=_pricing["price"],
            weight_g=int(item.get("weight_g") or 300),
            stock=int(item.get("stock") or 1000),
            warehouse="国内仓（义乌）",
            lead_days=3,
            skus=item.get("skus") or ["Default"],
            icon=item.get("icon") or "📦",
            hue=item.get("hue") or 210,
            content=content,
            sku_code=f"{prefix}-01",
            sku_prefix=prefix,
            source_url=item.get("url", ""),
            qualification=qual,
            qual_status="pending" if qual.get("required") else "none",
            images=(item.get("images") or [])[:8],
            freight_cny=float(item.get("freight_cny") or 0),
            price_rule=_pricing["formula"] if not _pricing["need_manual"] else _pricing["reason"],
            need_manual_price=_pricing["need_manual"],
        )

    # ---------- 回复生成 ----------
    def reply(self, intent: str, text: str, payload: Any = None) -> dict:
        if intent == "select":
            items = payload or []
            n = len(items)
            sales = sum(i["sales_30d"] for i in items)
            return self.add_log(
                "agent",
                f"已从 1688 开放平台筛出 **{n}** 个候选商品，合计 30 天销量 {sales:,}。"
                f"按「销量 + 采集人数 + 评分」排序，请勾选要提报的商品，确认后我生成提报内容。",
                {"type": "candidates", "items": items},
            )
        if intent == "publish":
            return self.add_log("agent", "好的，正在校验待提报草稿……", {"type": "publish_hint"})
        if intent == "status":
            running = [t for t in self.tasks.values() if t.status == "running"]
            done = [t for t in self.tasks.values() if t.status == "done"]
            return self.add_log(
                "agent",
                f"当前任务：进行中 {len(running)} 个，已完成 {len(done)} 个；"
                f"草稿 {len([d for d in self.drafts.values() if d.status == 'pending'])} 个待审核，"
                f"已提报 {len([d for d in self.drafts.values() if d.status in ('submitted', 'on_sale')])} 个。",
                {"type": "status"},
            )
        return self.add_log(
            "agent",
            "没太听懂这句。你可以直接说下面任意一种：\n\n"
            "- **选品**：「厨房类目挑 3 个」「宠物用品，不用资质的」\n"
            "- **加链接**：「把这个加了 http://detail.1688.com/offer/xxxx.html」\n"
            "- **看进度**：「现在有几个草稿」「哪些还没定价」\n\n"
            "如果每次都只回这段、不像在理解你——多半是**模型没配置或调用失败**，"
            "到「设置」检查 DeepSeek Key，或看页面顶部的状态提示。",
            {"type": "guide"},
        )


state = AgentState()
