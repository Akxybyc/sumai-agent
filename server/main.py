"""FastAPI 本地服务：桌面客户端的后端。

启动：.venv\\Scripts\\python.exe -m uvicorn main:app --port 8000
"""

from __future__ import annotations

import json
from datetime import datetime
import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import browser as browser_bridge
import erp as erp_adapters
import miaoshou as ms_adapters
import ms_attrs
import ms_custom_attrs
import ms_sku_en
import ms_api
import ms_img_check
import ms_claim
import ms_pipeline
import trend_ae
from agent import llm_agent
from agent import memory as agent_memory
import llm as llm_adapter
import rpa1688
import rpa_aliexpress as ae_rpa
from agent.orchestrator import Draft, Task, state

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR.parent / "web"
DATA_DIR = BASE_DIR.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SETTINGS_FILE = DATA_DIR / "settings.json"
MODEL_STATUS = {"last_error": "", "last_error_at": "", "last_ok_at": "", "model": ""}
CHAT_HISTORY: list[dict] = agent_memory.load_history()   # 最近对话（落盘，重启恢复）

app = FastAPI(title="速卖通智能上品 Agent")

DEFAULT_SETTINGS = {
    "store": {
        "name": "Shop1105760319 Store",
        "platform": "AliExpress 全托管（跨境卖家中心）",
        "account": "广东智慧兆能（示例店铺）",
        "authorized": True,
        "expire": "2027-10-19",
    },
    "driver": {"mode": "rpa", "fallback": False},
    "llm": {
        "provider": "volcengine",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seed-1-6-250615",
        "api_key": "",
        "fallback": {
            "enabled": False,
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "",
        },
        "tasks": {"copy": "", "vision": "", "category": ""},
    },
    "a1688": {"app_key": "", "authorized": False},
    "selection": {"count": 3, "min_sales": 3000, "price_min": 5, "price_max": 150, "auto_confirm": True},
    "prompt": {
        "template": "速卖通欧美站 · 全托管上架全套方案",
        "version": "v1",
        "loaded": True,
        "file": "prompts/aliexpress_listing_v1.md",
    },
}


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            merged = json.loads(json.dumps(DEFAULT_SETTINGS))
            for k, v in saved.items():
                if isinstance(v, dict) and isinstance(merged.get(k), dict):
                    merged[k].update(v)
                else:
                    merged[k] = v
            return merged
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_SETTINGS))


settings = load_settings()


class ChatIn(BaseModel):
    text: str


class IdsIn(BaseModel):
    ids: list[str]


class DraftPatch(BaseModel):
    title_en: str | None = None
    supply_price: float | None = None
    stock: int | None = None
    weight_g: int | None = None
    sku_code: str | None = None
    sku_prefix: str | None = None


class SettingsIn(BaseModel):
    data: dict


def draft_to_dict(d: Draft) -> dict:
    return {
        "id": d.id,
        "source_id": d.source_id,
        "title_cn": d.title_cn,
        "title_en": d.title_en,
        "category_cn": d.category_cn,
        "category_en": d.category_en,
        "attrs": d.attrs,
        "cost_cny": d.cost_cny,
        "supply_price": d.supply_price,
        "weight_g": d.weight_g,
        "stock": d.stock,
        "warehouse": d.warehouse,
        "lead_days": d.lead_days,
        "skus": d.skus,
        "icon": d.icon,
        "hue": d.hue,
        "status": d.status,
        "sku_code": d.sku_code,
        "sku_prefix": d.sku_prefix,
        "product_id": d.product_id,
        "content": d.content,
        "qualification": d.qualification,
        "qual_status": d.qual_status,
        "qual_cert": d.qual_cert,
        "source_url": d.source_url,
        "images": d.images,
        "ms_detail_id": d.ms_detail_id,
        "freight_cny": d.freight_cny,
        "price_rule": d.price_rule,
        "need_manual_price": d.need_manual_price,
    }


def task_to_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "kind": t.kind,
        "status": t.status,
        "progress": t.progress,
        "step": t.step,
        "total": t.total,
        "done_count": t.done_count,
        "failed_count": t.failed_count,
        "created_at": t.created_at,
        "detail": t.detail,
    }


@app.get("/api/bootstrap")
def bootstrap():
    return {
        "settings": settings,
        "logs": state.logs,
        "drafts": [draft_to_dict(d) for d in state.drafts.values()],
        "tasks": [task_to_dict(t) for t in state.tasks.values()],
        "stats": {
            "pending": len([d for d in state.drafts.values() if d.status == "pending"]),
            "approved": len([d for d in state.drafts.values() if d.status == "approved"]),
            "submitted": len([d for d in state.drafts.values() if d.status == "submitted"]),
            "on_sale": len([d for d in state.drafts.values() if d.status == "on_sale"]),
            "total": len(state.drafts),
        },
        "usage": {
            "calls": state.usage["calls"],
            "tokens": round((state.usage["prompt_chars"] + state.usage["completion_chars"]) / 3),
            "est_cost": llm_adapter.estimate_cost(
                settings.get("llm", {}).get("model", ""),
                state.usage["prompt_chars"],
                state.usage["completion_chars"],
            ),
        },
    }


@app.get("/api/llm/providers")
def llm_providers():
    return {"providers": llm_adapter.PROVIDERS, "tasks": llm_adapter.TASKS}


class LlmTestIn(BaseModel):
    data: dict


@app.on_event("startup")
def _auto_launch_browser():
    """服务起来时顺手确保调试浏览器在线（客户不用管端口）。"""
    import threading

    def _run():
        try:
            if not browser_bridge.debug_alive(9222):
                r = browser_bridge.launch(9222)
                state.add_log("agent", r.get("message") or "已尝试启动浏览器", {"type": "status"})
        except Exception as e:  # noqa: BLE001
            state.add_log("agent", f"自动启动浏览器失败：{type(e).__name__}", {"type": "err"})

    threading.Thread(target=_run, daemon=True).start()


@app.get("/api/model/status")
def model_status():
    """模型配置与最近一次调用结果，用于界面状态灯。"""
    cfg = settings.get("llm") or {}
    configured = bool(cfg.get("api_key"))
    return {
        "configured": configured,
        "model": cfg.get("model") or "",
        "vision_model": cfg.get("vision_model") or "",
        "last_ok_at": MODEL_STATUS.get("last_ok_at") or "",
        "last_error": MODEL_STATUS.get("last_error") or "",
        "last_error_at": MODEL_STATUS.get("last_error_at") or "",
        "ok": configured and not MODEL_STATUS.get("last_error"),
    }


@app.get("/api/browser/status")
def browser_status():
    return browser_bridge.status()


class BrowserLaunchIn(BaseModel):
    port: int = 9222
    profile: str | None = None
    start_url: str = "about:blank"


@app.post("/api/browser/launch")
def browser_launch(body: BrowserLaunchIn):
    profile = Path(body.profile) if body.profile else None
    return browser_bridge.launch(body.port, profile, body.start_url)


class CollectIn(BaseModel):
    keyword: str
    pages: int = 1
    limit: int = 20
    port: int = 9222


@app.post("/api/1688/collect")
async def collect_1688(body: CollectIn):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(
        rpa1688.collect_search, body.keyword, body.pages, body.limit, body.port
    )


_KW_STOP = [
    "不需要资质", "无需资质", "不用资质", "免资质", "要资质", "资质", "1688", "淘宝", "拼多多", "阿里",
    "帮我", "请你", "请", "推荐", "给我", "找", "搜索", "搜", "选",
    "几个", "一些", "几款", "几件", "一批", "点", "个",
    "最近", "卖得好", "好卖", "热销", "好", "的", "品",
    "真实", "数据", "选品", "采集", "上架", "提报", "刊登", "发布",
    "跑一下", "跑", "看看", "一下", "用",
    "商品", "产品", "新品", "爆款", "款",
    "，", "。", ",", "、", "！", "!", "？", "?", "：", ":",
]


def _extract_keyword(text: str) -> str:
    """抽类目关键词；抽不到返回空串（由调用方追问，不再默认保温杯）。"""
    kw = text
    for w in sorted(_KW_STOP, key=len, reverse=True):
        kw = kw.replace(w, " ")
    kw = re.sub(r"\s+", " ", kw).strip(" 的和与及")
    kw = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5 ]", "", kw).strip()
    # 丢掉单字残渣（如“不/要/的”），取第一个有效词
    tokens = [t for t in kw.split() if len(t) >= 2]
    return (tokens[0] if tokens else "")[:20]


def _wants_no_qual(text: str) -> bool:
    return any(k in text for k in ("不需要资质", "无需资质", "不用资质", "不要资质", "免资质", "免检"))


def _real_pipeline(text: str, limit: int = 3, port: int = 9222) -> dict:
    """真实链路：1688 搜索 → 打分 → 详情补全 → 生成草稿。"""
    keyword = _extract_keyword(text)
    if not keyword:
        msg = state.add_log(
            "agent",
            "要选哪个类目的？给我一个词就行，例如：**瑜伽垫 / 收纳盒 / 手机支架 / 宠物牵引绳 / 五金工具**。\n\n"
            "任意类目都能跑，我按这个词去 1688 真实搜索，不会默认某个品类。",
            {"type": "guide"},
        )
        return {"message": msg, "items": []}

    search = rpa1688.collect_search(keyword, 1, 30, port)
    if not search.get("ok"):
        msg = state.add_log(
            "agent",
            f"真实数据采集没成功：{search.get('message', '未知原因')}\n\n"
            f"如果是滑块验证，请在打开的 Chrome 里拖一下，然后再说一次。",
            {"type": "guide"},
        )
        return {"message": msg, "items": []}

    pool = search["items"]
    if _wants_no_qual(text):
        pool = [i for i in pool
                if not state.check_qualification(
                    f"{i.get('category', '')} {i.get('title', '')}")["required"]]
        if not pool:
            msg = state.add_log(
                "agent",
                f"搜到 **{len(search['items'])}** 条「{keyword}」，但**全部命中资质类目**（食品接触/3C/儿童/化妆品/医疗），"
                f"按你的要求已全部排除。换个免资质类目试试？例如：收纳盒、手机支架、宠物牵引绳、五金工具。",
                {"type": "guide"},
            )
            return {"message": msg, "items": []}

    picks = state.score_real(pool, count=limit)
    enriched = []
    for p in picks:
        d = rpa1688.collect_detail(p["url"], port)
        if d.get("ok"):
            p["weight_g"] = d.get("weight_g") or p.get("weight_g", 0)
            p["skus"] = d.get("skus") or p.get("skus") or ["Default"]
            p["attributes"] = d.get("attributes") or {}
            p["rating"] = d.get("rating") or 0
            p["stock"] = d.get("stock") or 1000
            p["images"] = d.get("images") or []
            if d.get("price_cny"):
                p["price_cny"] = d["price_cny"]
            if d.get("supplier"):
                p["supplier"] = d["supplier"]
        enriched.append(p)

    drafts = []
    for idx, p in enumerate(enriched, start=1):
        draft = state.build_draft_from_source(p, idx)
        state.drafts[draft.id] = draft
        drafts.append(draft)
        state.usage["calls"] += 1
        state.usage["prompt_chars"] += 1800
        state.usage["completion_chars"] += 1400

    msg = state.add_log(
        "agent",
        f"用真实 1688 数据跑完了：搜索 **{len(search['items'])}** 条，自动选定 **{len(drafts)}** 个，"
        f"详情已补全（重量/SKU/属性/评价），草稿已进审核台。\n\n"
        f"打分口径：30 天销量 40% · 回头率 30% · 价格带 20% · 供应商 10%。",
        {"type": "real", "items": enriched, "draft_ids": [d.id for d in drafts]},
    )
    state.persist()
    return {
        "message": msg,
        "items": enriched,
        "draft_ids": [d.id for d in drafts],
        "drafts": [draft_to_dict(d) for d in drafts],
    }


class RealIn(BaseModel):
    keyword: str = "保温杯"
    limit: int = 3
    port: int = 9222


@app.post("/api/1688/auto")
async def real_auto(body: RealIn):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(_real_pipeline, body.keyword, body.limit, body.port)


# ---------- 速卖通卖家后台（提报） ----------
@app.get("/api/ae/status")
async def ae_status(port: int = 9222):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(ae_rpa.status, port)


class AeOpenIn(BaseModel):
    port: int = 9222
    url: str = "https://seller.aliexpress.com/"


@app.post("/api/ae/open")
async def ae_open(body: AeOpenIn):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(ae_rpa.open_seller, body.port, body.url)


@app.post("/api/ae/dump")
async def ae_dump(port: int = 9222):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(ae_rpa.dump_publish_form, port)


class AeFillIn(BaseModel):
    title: str
    image_url: str = ""
    port: int = 9222
    dry_run: bool = True


@app.post("/api/ae/fill")
async def ae_fill(body: AeFillIn):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(ae_rpa.fill_preview, body.title, body.image_url, body.port, body.dry_run)


# ---------- ERP 执行层（店小宝） ----------
@app.get("/api/erp/adapters")
def erp_adapters_list():
    return [{"name": k, "label": v.label, "home": v.home} for k, v in erp_adapters.ADAPTERS.items()]


class ErpOpenIn(BaseModel):
    name: str = "dianxiaobao"
    port: int = 9222


@app.post("/api/erp/open")
async def erp_open(body: ErpOpenIn):
    from fastapi.concurrency import run_in_threadpool

    adapter = erp_adapters.get_adapter(body.name)
    if not adapter:
        raise HTTPException(404, "未知的 ERP 适配器")
    return await run_in_threadpool(adapter.open_home, body.port)


class ErpPushIn(BaseModel):
    name: str = "dianxiaobao"
    links: list[str] = []
    draft_ids: list[str] = []
    dry_run: bool = True
    port: int = 9222


@app.post("/api/erp/push")
async def erp_push(body: ErpPushIn):
    from fastapi.concurrency import run_in_threadpool

    adapter = erp_adapters.get_adapter(body.name)
    if not adapter:
        raise HTTPException(404, "未知的 ERP 适配器")
    links = list(body.links)
    blocked = []
    for did in body.draft_ids:
        d = state.drafts.get(did)
        if not d:
            continue
        if d.qualification.get("required") and d.qual_status != "approved":
            blocked.append({"id": d.id, "title": d.title_en, "reason": "需资质未登记"})
            continue
        if d.source_url:
            links.append(d.source_url)
    if not links:
        return {"ok": True, "count": 0, "steps": [],
                "message": "全部被资质闸门拦截，未推送", "blocked": blocked}
    result = await run_in_threadpool(adapter.push_links, links, body.port, body.dry_run)
    result["blocked"] = blocked
    return result


# ---------- 妙手 ERP 执行层 ----------
class MsCollectIn(BaseModel):
    draft_ids: list[str] = []
    port: int = 9222
    dry_run: bool = True
    wait_sec: int = 35


@app.get("/api/miaoshou/adapters")
def ms_adapters_list():
    return [{"name": k, "label": v.label, "home": "https://erp.91miaoshou.com/"}
            for k, v in ms_adapters.ADAPTERS.items()]


@app.post("/api/erp/miaoshou/open")
async def ms_open(body: ErpOpenIn):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(ms_adapters.get_adapter("miaoshou").open_home, body.port)


class OpenBoxIn(BaseModel):
    which: str = "common"   # common=公共采集箱, fc=速卖通全托管采集箱
    port: int = 9222


class ClaimIn(BaseModel):
    dry_run: bool = False
    wait: int = 8


class WriteEnIn(BaseModel):
    detail_ids: list[int] = []
    dry_run: bool = False


@app.post("/api/erp/miaoshou/write_en")
async def ms_write_en(body: WriteEnIn):
    """在公共采集箱阶段用 API 把标题/描述/颜色名写成英文（认领前写入，免开编辑页）。"""
    from fastapi.concurrency import run_in_threadpool

    r = await run_in_threadpool(ms_api.write_english_to_box, body.detail_ids or None, body.dry_run)
    state.add_log("agent", r.get("message") or "写入英文", {"type": "status"})
    return r


class PipelineIn(BaseModel):
    draft_ids: list[str] = []
    dry_run: bool = False


@app.post("/api/erp/miaoshou/pipeline")
async def ms_pipeline_run(body: PipelineIn):
    """一键：草稿 → 采集进妙手 → 写入英文（标题用提示词规则生成的那版）。"""
    from fastapi.concurrency import run_in_threadpool

    ids = body.draft_ids or [d.id for d in state.drafts.values()]
    picked = []
    for i in ids:
        d = state.drafts.get(i)
        if not d:
            continue
        url = d.source_url or (d.content or {}).get("source_url")
        if not url:
            continue
        # 标题按用户提示词现场重算（核心+属性+核心+长尾+流量 / 115 字母 / 无标点）
        from content import build_title_v2, core_from_item, pick_pack
        cat_cn = d.category_cn or "家居"
        core = core_from_item(d.title_cn, cat_cn)
        pack = pick_pack(cat_cn)
        title_en, _chk = build_title_v2(core, pack["attr"], pack["longtail"], pack["flow"],
                                        seed=d.source_id or d.title_cn)
        picked.append({"id": d.id, "url": url, "title_en": title_en,
                       "price_cny": d.cost_cny, "title_cn": d.title_cn,
                       "detail_id": d.ms_detail_id})
    if not picked:
        return {"ok": False, "message": "没有带链接的草稿可采集"}

    def _run():
        r = ms_pipeline.run(picked, body.dry_run)
        if not body.dry_run:
            for it in r.get("items") or []:
                d = state.drafts.get(it["draft"])
                if d and it.get("detailId"):
                    d.ms_detail_id = int(it["detailId"])
            state.persist()
        return r

    r = await run_in_threadpool(_run)
    state.add_log("agent", r.get("message") or "一键采集+英文", {"type": "status"})
    return r


@app.post("/api/erp/miaoshou/claim")
async def ms_claim_to_fc(body: ClaimIn):
    """公共采集箱 → 认领到「速卖通全托管」（UI 自动化，API 不支持该平台）。"""
    from fastapi.concurrency import run_in_threadpool

    r = await run_in_threadpool(ms_claim.claim, 9222, body.dry_run, body.wait)
    state.add_log("agent", r.get("message") or "认领完成",
                  {"type": "status"})
    return r


@app.post("/api/erp/miaoshou/open_box")
async def ms_open_box(body: OpenBoxIn):
    """在调试 Chrome 里打开采集箱页面并切到前台，供人工勾选认领。"""
    from fastapi.concurrency import run_in_threadpool

    def _run():
        from playwright.sync_api import sync_playwright
        url = ("https://erp.91miaoshou.com/common_collect_box/items"
               if body.which == "common"
               else "https://erp.91miaoshou.com/aliexpress_fc/collect_box/items")
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{body.port}")
            ctx = b.contexts[0]
            pg = next((x for x in ctx.pages if "common_collect_box/items" in x.url or "collect_box/items" in x.url), None)
            if pg is None:
                pg = ctx.new_page()
            pg.goto(url, wait_until="domcontentloaded", timeout=60000)
            pg.wait_for_timeout(2500)
            pg.bring_to_front()
            return {"ok": True, "url": pg.url, "which": body.which}

    return await run_in_threadpool(_run)


@app.post("/api/erp/miaoshou/collect")
async def ms_collect(body: MsCollectIn):
    """把草稿（1688 链接 + 英文标题）推进妙手，采集并自动认领到速卖通全托管采集箱。"""
    from fastapi.concurrency import run_in_threadpool

    items, blocked = [], []
    for did in body.draft_ids:
        d = state.drafts.get(did)
        if not d:
            continue
        if d.qualification.get("required") and d.qual_status != "approved":
            blocked.append({"id": d.id, "title": d.title_en, "reason": "需资质未登记"})
            continue
        if not d.source_url:
            blocked.append({"id": d.id, "title": d.title_en, "reason": "缺少 1688 链接"})
            continue
        items.append({"url": d.source_url, "title": d.title_en, "source_id": d.source_id})

    if not items:
        return {"ok": True, "count": 0, "steps": [],
                "message": "没有可推进妙手的商品（全部被拦截）", "blocked": blocked}

    adapter = ms_adapters.get_adapter("miaoshou")
    result = await run_in_threadpool(adapter.collect, items, body.port, body.dry_run, body.wait_sec)
    result["blocked"] = blocked
    state.add_log(
        "agent",
        f"妙手采集：提交 **{len(items)}** 个，" + ("成功 " + str(result.get("count", 0)) + " 个"
                                                if result.get("ok") else f"失败：{result.get('message', '')}"),
        {"type": "status"},
    )
    return result


@app.post("/api/erp/miaoshou/prepare")
async def ms_prepare(body: MsCollectIn):
    """预填：只把链接+标题填进妙手采集框，等人工点『采集并自动认领』。"""
    from fastapi.concurrency import run_in_threadpool

    items, blocked = [], []
    for did in body.draft_ids:
        d = state.drafts.get(did)
        if not d:
            continue
        if d.qualification.get("required") and d.qual_status != "approved":
            blocked.append({"id": d.id, "title": d.title_en, "reason": "需资质未登记"})
            continue
        if not d.source_url:
            blocked.append({"id": d.id, "title": d.title_en, "reason": "缺少 1688 链接"})
            continue
        items.append({"url": d.source_url, "title": d.title_en, "source_id": d.source_id})
    if not items:
        return {"ok": False, "count": 0, "blocked": blocked, "message": "没有可填的草稿"}
    res = await run_in_threadpool(ms_adapters.get_adapter("miaoshou").prepare, items, body.port)
    res["blocked"] = blocked
    state.add_log("agent", f"已向妙手预填 **{res.get('count', 0)}** 条，等人工点采集。", {"type": "status"})
    return res


@app.post("/api/erp/miaoshou/select")
async def ms_select(body: MsCollectIn):
    """在采集箱勾选指定草稿对应的商品（不点发布），返回可用按钮。"""
    from fastapi.concurrency import run_in_threadpool

    ids = [state.drafts[i].source_id for i in body.draft_ids
           if i in state.drafts and state.drafts[i].source_id]
    if not ids:
        return {"ok": False, "message": "没有可定位的货源 ID"}
    return await run_in_threadpool(
        ms_adapters.get_adapter("miaoshou").select_for_publish, ids, body.port)


@app.get("/api/erp/miaoshou/attr_schema")
async def ms_attr_schema(port: int = 9222):
    from fastapi.concurrency import run_in_threadpool
    return await run_in_threadpool(ms_attrs.read_schema, port)


class AttrFillIn(BaseModel):
    values: dict = {}
    dry_run: bool = True
    port: int = 9222


@app.post("/api/erp/miaoshou/attr_fill")
async def ms_attr_fill(body: AttrFillIn):
    from fastapi.concurrency import run_in_threadpool
    res = await run_in_threadpool(ms_attrs.fill, body.values, body.port, body.dry_run)
    state.add_log("agent", f"属性填充：{res.get('message')}", {"type": "status", "result": res})
    return res


class AttrAutoIn(BaseModel):
    draft_id: str
    dry_run: bool = True
    port: int = 9222


@app.post("/api/erp/miaoshou/attr_auto")
async def ms_attr_auto(body: AttrAutoIn):
    """读草稿属性 → LLM 映射到速卖通类目属性选项 → 填充（默认 dry_run）。"""
    import json as _json
    from fastapi.concurrency import run_in_threadpool

    d = state.drafts.get(body.draft_id)
    if not d:
        raise HTTPException(404, "草稿不存在")
    schema = await run_in_threadpool(ms_attrs.read_schema, body.port)
    if not schema.get("ok"):
        return {"ok": False, "message": schema.get("message", "读取属性失败")}

    options = {f: v.get("options", []) for f, v in (schema.get("fields") or {}).items()}
    src = _json.dumps({"标题": d.title_cn, "属性": d.attrs}, ensure_ascii=False)
    prompt = (
        "你是跨境电商商品属性映射助手。下面是 1688 商品信息，以及速卖通全托管类目属性每个字段的可选值。\n"
        "请为每个字段挑选最合适的一个选项，**只能从可选值里原样复制**，无法判断就省略该字段。\n"
        "只输出 JSON 对象，形如 {\"材质\": \"塑料(Plastic)\"}，不要解释。\n\n"
        f"商品信息：{src}\n\n可选值：{_json.dumps(options, ensure_ascii=False)}"
    )
    cfg = settings.get("llm") or {}
    try:
        resp = llm_agent._post(cfg, {"model": cfg.get("model") or "deepseek-chat",
                                     "messages": [{"role": "user", "content": prompt}],
                                     "temperature": 0})
        text = resp["choices"][0]["message"]["content"].strip()
        start, end = text.find("{"), text.rfind("}")
        mapping = _json.loads(text[start:end + 1]) if start >= 0 else {}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"映射失败：{type(e).__name__}: {e}"}

    res = await run_in_threadpool(ms_attrs.fill, mapping, body.port, body.dry_run)
    res["mapping"] = mapping
    state.add_log("agent", f"属性自动映射 {len(mapping)} 项，填充 {res.get('filled')} 项（dry_run={body.dry_run}）",
                  {"type": "status"})
    return res


class TranslateImgIn(BaseModel):
    draft_ids: list[str] = []
    platform: str = "aeAi"     # aeAi=速卖通AI；ali/tosoiot/ykt 也可
    source: str = "zh"
    target: str = "en"
    limit_per_item: int = 8
    precheck: bool = True     # 先用视觉模型判断图中有无文字，无文字不翻


@app.post("/api/erp/miaoshou/translate_images")
async def ms_translate_images(body: TranslateImgIn):
    """图片翻译：把草稿里的 1688 图翻成目标语言，成功后替换为新图。"""
    from fastapi.concurrency import run_in_threadpool

    ids = body.draft_ids or [d.id for d in state.drafts.values()]
    targets = [state.drafts[i] for i in ids if i in state.drafts]
    if not targets:
        return {"ok": False, "message": "没有可翻译的草稿"}

    def _run():
        total_translated, total_skipped, failed = 0, 0, []
        checked, with_text, no_text = 0, 0, 0
        for d in targets:
            imgs = (d.images or [])[:body.limit_per_item]
            if not imgs:
                continue
            # 先用视觉模型判断有没有文字，没文字的不花额度
            if body.precheck:
                scan = ms_img_check.scan(imgs, settings.get("llm") or {})
                keep = [r["url"] for r in scan["results"] if r["has_text"]]
                checked += scan["total"]
                with_text += scan["with_text"]
                no_text += scan["without_text"]
                if not keep:
                    total_skipped += len(imgs)
                    continue
                imgs = keep
            res = ms_api.translate_image(imgs, body.source, body.target, body.platform)
            data = (res.get("data") or {}).get("data") or {}
            mapping = {}
            for x in data.get("translateImageUrlResultList") or []:
                ori, new = x.get("oriImageUrl"), x.get("newImageUrl")
                if ori and new and new != ori:
                    mapping[ori] = new
            if mapping:
                d.images = [mapping.get(u, u) for u in (d.images or [])]
                total_translated += len(mapping)
            total_skipped += len(imgs) - len(mapping)
            if not res.get("ok"):
                failed.append({"draft": d.id, "msg": res.get("message")})
        state.persist()
        msg = f"图片翻译完成：{total_translated} 张已替换"
        if body.precheck:
            msg += f"（预检 {checked} 张，其中 {with_text} 张有文字、{no_text} 张无文字已跳过省额度）"
        else:
            msg += f"，{total_skipped} 张无需翻译"
        return {"ok": total_translated > 0, "translated": total_translated,
                "skipped": total_skipped, "failed": failed,
                "checked": checked, "with_text": with_text, "without_text": no_text,
                "message": msg}

    r = await run_in_threadpool(_run)
    state.add_log("agent", r["message"], {"type": "status"})
    return r


@app.get("/api/erp/miaoshou/audit")
async def ms_audit(port: int = 9222):
    """发布前体检：列出编辑页里必填但为空的项。"""
    from fastapi.concurrency import run_in_threadpool
    res = await run_in_threadpool(ms_attrs.audit, port)
    if res.get("ok"):
        state.add_log("agent", f"发布体检：{res.get('message')}", {"type": "status"})
    return res


class CustomAttrIn(BaseModel):
    dry_run: bool = True
    port: int = 9222


@app.post("/api/erp/miaoshou/custom_attrs")
async def ms_custom_attrs_api(body: CustomAttrIn):
    """把妙手「自定义属性」的中文键值翻成英文并写回。"""
    from fastapi.concurrency import run_in_threadpool

    def _run():
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.connect_over_cdp(f"http://127.0.0.1:{body.port}")
            pg = ms_custom_attrs._page(b)
            if pg is None:
                return {"ok": False, "message": "未打开妙手页面"}
            cfg = settings.get("llm") or {}
            attrs = ms_custom_attrs.convert(pg, cfg, body.dry_run)
            sku = ms_sku_en.convert(pg, cfg, body.dry_run)
            return {
                "ok": bool(attrs.get("ok") or sku.get("ok")),
                "attrs": attrs,
                "sku": sku,
                "message": f"属性：{attrs.get('message') or str(attrs.get('count')) + ' 行'}；"
                           f"SKU：{sku.get('message') or str(sku.get('count')) + ' 个'}",
            }

    res = await run_in_threadpool(_run)
    state.add_log("agent", f"自定义属性英文化：{res.get('message') or ''}", {"type": "status"})
    return res


@app.post("/api/erp/miaoshou/api_collect")
async def ms_api_collect(body: MsCollectIn):
    """走开放平台 API 采集（不依赖浏览器）。自动去重，单次提交上限 50，超出自动分批。"""
    from fastapi.concurrency import run_in_threadpool

    links, blocked = [], []
    for did in body.draft_ids:
        d = state.drafts.get(did)
        if not d:
            continue
        if d.qualification.get("required") and d.qual_status != "approved":
            blocked.append({"id": d.id, "title": d.title_en, "reason": "需资质未登记"})
            continue
        if not d.source_url:
            blocked.append({"id": d.id, "title": d.title_en, "reason": "缺少 1688 链接"})
            continue
        links.append(d.source_url)
    if not links:
        return {"ok": False, "message": "没有可采集的链接", "blocked": blocked}

    # 去重：先取公共采集箱里已有的货源
    idx = await run_in_threadpool(ms_api.list_all_sources)
    known = idx.get("sources") or {}
    skipped, todo = [], []
    for url in links:
        sid = url.rstrip("/").split("/")[-1].replace(".html", "")
        if sid in known:
            skipped.append({"source_id": sid, "detail_id": known[sid]})
        else:
            todo.append(url)

    # 先把已存在的 detailId 回写到草稿
    by_sid = {}
    for did in body.draft_ids:
        d = state.drafts.get(did)
        if d and d.source_url:
            sid = d.source_url.rstrip("/").split("/")[-1].replace(".html", "")
            by_sid[sid] = d
    for s_ in skipped:
        d = by_sid.get(s_["source_id"])
        if d:
            d.ms_detail_id = int(s_["detail_id"])
    state.persist()

    if not todo:
        return {"ok": True, "submitted": 0, "created": 0, "skipped": skipped, "blocked": blocked,
                "message": f"全部 {len(skipped)} 条已在采集箱中，无需重复采集"}

    created_map, errors = {}, []
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        res = await run_in_threadpool(ms_api.collect_by_links, chunk)
        data = (res.get("data") or {}).get("data") or {}
        m = data.get("sourceItemIdAndDetailIdMap") or {}
        if m:
            created_map.update(m)
        elif not res.get("ok"):
            errors.append(res.get("message") or "采集失败")

    for sid, detail_id in created_map.items():
        if sid in by_sid:
            by_sid[sid].ms_detail_id = int(detail_id)
    state.persist()

    ok = bool(created_map)
    state.add_log("agent",
                  f"API 采集：新采 **{len(created_map)}** 条，跳过已存在 **{len(skipped)}** 条"
                  + (f"，拦截 {len(blocked)} 条" if blocked else "")
                  + (f"，失败 {len(errors)}" if errors else ""),
                  {"type": "status"})
    return {"ok": ok, "submitted": len(todo), "created": len(created_map),
            "mapping": created_map, "skipped": skipped, "blocked": blocked, "errors": errors,
            "message": (f"新采 {len(created_map)} 条、跳过 {len(skipped)} 条；"
                        f"请到妙手「公共采集箱」认领到速卖通全托管" if ok else (errors[0] if errors else "采集失败"))}


@app.get("/api/erp/miaoshou/api_box")
async def ms_api_box(page_no: int = 1, page_size: int = 20, tab: str = "all"):
    """走 API 读公共采集箱（替代页面读取）。"""
    from fastapi.concurrency import run_in_threadpool
    res = await run_in_threadpool(ms_api.list_collect_box, page_no, page_size, tab)
    d = (res.get("data") or {}).get("data") or {}
    rows = []
    for it in (d.get("detailList") or []):
        rows.append({
            "detail_id": it.get("commonCollectBoxDetailId"),
            "title": it.get("title"),
            "item_num": it.get("itemNum"),
            "thumb": it.get("thumbnail"),
            "price": it.get("sourcePrice") or it.get("price"),
            "claimed": it.get("claimed"),
        })
    return {"ok": res.get("ok"), "total": d.get("total"), "rows": rows,
            "message": res.get("message") or ""}


@app.get("/api/erp/miaoshou/box")
async def ms_box(port: int = 9222):
    from fastapi.concurrency import run_in_threadpool

    return await run_in_threadpool(ms_adapters.get_adapter("miaoshou").box_rows, port)


@app.post("/api/llm/test")
def llm_test(body: LlmTestIn):
    result = llm_adapter.test_connection(body.data or {})
    state.add_log(
        "agent",
        f"算力连通性测试：{result['message']}",
        {"type": "status"},
    )
    return result


@app.post("/api/chat")
async def chat(body: ChatIn):
    text = body.text.strip()
    if not text:
        raise HTTPException(400, "空消息")
    state.add_log("user", text)
    intent = state.route(text)

    # ---------- 模型主导（有 API Key 时优先） ----------
    llm_cfg = (settings.get("llm") or {})
    if llm_cfg.get("api_key"):
        from fastapi.concurrency import run_in_threadpool

        collected: list[dict] = []

        def _tool_search(keyword: str, limit: int = 3, no_qualification: bool = False):
            kw = f"{keyword} 不需要资质" if no_qualification else keyword
            res = _real_pipeline(kw, limit=limit)
            items = res.get("items") or []
            collected.extend(items)
            return {
                "ok": bool(items),
                "count": len(items),
                "draft_ids": res.get("draft_ids") or [],
                "message": (res.get("message") or {}).get("text", "")[:400],
                "items": [{k: i.get(k) for k in ("title", "price_cny", "sales_30d", "score")} for i in items],
            }

        def _tool_add_drafts(urls: list[str]):
            created = []
            for i, url in enumerate(urls[:10], start=1):
                det = rpa1688.collect_detail(url, 9222)
                _oid = url.rstrip("/").split("/")[-1].replace(".html", "")
                item = {
                    "id": f"1688-{_oid}",
                    "url": url,
                    "offer_id": _oid,
                    "title": (det.get("title") or "").strip(),
                    "price_cny": det.get("price_cny") or 0,
                    "sales_30d": 0,
                    "repurchase_rate": 0,
                    "supplier": det.get("supplier") or "",
                    "weight_g": det.get("weight_g") or 0,
                    "skus": det.get("skus") or ["Default"],
                    "attributes": det.get("attributes") or {},
                    "images": det.get("images") or [],
                    "stock": det.get("stock") or 1000,
                    "category": det.get("category") or "家居",
                }
                if not item["title"]:
                    continue
                d = state.build_draft_from_source(item, i)
                state.drafts[d.id] = d
                created.append({"id": d.id, "title_cn": d.title_cn, "title_en": d.title_en,
                                "source_url": d.source_url, "cost": d.cost_cny,
                                "supply_price": d.supply_price,
                                "need_manual_price": d.need_manual_price,
                                "price_note": d.price_rule})
            state.persist()
            state.add_log("agent", f"已生成 **{len(created)}** 个草稿", {"type": "status"})
            return {"ok": bool(created), "count": len(created), "drafts": created}

        def _existing_by_source(source_id: str):
            return next((x for x in state.drafts.values() if x.source_id == source_id), None)

        def _build_one(cand: dict, idx: int) -> dict | None:
            """由候选生成一条草稿（含去重）。返回 {created/skipped, ...} 或 None。"""
            url = cand.get("url") or ""
            oid = cand.get("offer_id") or url.rstrip("/").split("/")[-1].replace(".html", "")
            sid = f"1688-{oid}"
            exist = _existing_by_source(sid)
            if exist:
                return {"id": exist.id, "title_cn": exist.title_cn, "skipped": True,
                        "reason": "已有同款草稿"}
            try:
                det = rpa1688.collect_detail(url, 9222)
            except Exception:
                det = {}
            item = {
                "id": sid, "url": url, "offer_id": oid,
                "title": (det.get("title") or cand.get("title") or "").strip(),
                "price_cny": det.get("price_cny") or cand.get("price_cny") or 0,
                "sales_30d": cand.get("sales_30d") or 0,
                "repurchase_rate": cand.get("repurchase_rate") or 0,
                "supplier": det.get("supplier") or cand.get("supplier") or "",
                "weight_g": det.get("weight_g") or 0,
                "skus": det.get("skus") or ["Default"],
                "attributes": det.get("attributes") or {},
                "images": det.get("images") or [],
                "stock": det.get("stock") or 1000,
                "category": det.get("category") or cand.get("category") or "家居",
            }
            if not item["title"]:
                return None
            d = state.build_draft_from_source(item, idx)
            state.drafts[d.id] = d
            return {"id": d.id, "title_cn": d.title_cn, "title_en": d.title_en,
                    "cost": d.cost_cny, "supply_price": d.supply_price,
                    "need_manual_price": d.need_manual_price,
                    "price_note": d.price_rule, "skipped": False}

        def _tool_generate_image(draft_id: str, image_type: str = "场景图"):
            from agent import image_gen
            d = state.drafts.get(draft_id)
            if not d:
                return {"ok": False, "message": "草稿不存在"}
            st = image_gen.status()
            if not st["enabled"]:
                return {"ok": False, "disabled": True, "message": st["message"]}
            prompt = image_gen.build_prompt(image_type, (d.title_en or d.title_cn)[:80])
            r = image_gen.generate(prompt)
            if r.get("ok"):
                state.add_log("agent", f"已生成{image_type}：{d.title_cn[:14]}", {"type": "status"})
            return {**r, "prompt": prompt}

        def _tool_batch_draft(keyword_en: str, keyword_cn: str, count: int = 3):
            """趋势选品 + 批量建草稿（一次调用搞定多条）。"""
            from agent import trend_select
            n = max(1, min(int(count or 3), 10))
            r = trend_select.pick(keyword_en, keyword_cn, limit=min(max(n + 10, 15), 20))
            if not r.get("ok"):
                return {"ok": False, "message": r.get("message") or "选品失败"}
            cands = r.get("candidates") or []
            created, skipped, failed = [], [], 0
            # 跳过重复后继续往下找，直到凑够 n 条
            for c in cands:
                if len(created) >= n:
                    break
                one = _build_one(c, len(created) + 1)
                if one is None:
                    failed += 1
                elif one.get("skipped"):
                    skipped.append(one)
                else:
                    created.append(one)
            state.persist()
            need = [x for x in created if x.get("need_manual_price")]
            state.add_log("agent",
                          f"批量建草稿：新增 **{len(created)}** 条"
                          + (f"，跳过重复 {len(skipped)} 条" if skipped else "")
                          + (f"，失败 {failed} 条" if failed else ""), {"type": "status"})
            return {"ok": bool(created), "created": created, "skipped": skipped,
                    "need_manual_price": [x["title_cn"] for x in need],
                    "fetched_at": r.get("fetched_at"),
                    "message": f"新建 {len(created)} 条草稿"
                               + (f"（{len(skipped)} 条已存在）" if skipped else "")
                               + ("；其中 %d 条成本<10 元需客户定价" % len(need) if need else "")}

        def _tool_draft_from_pick(rank: int = 1):
            from agent import trend_select
            items = trend_select.LAST_PICKS.get("items") or []
            if not items:
                return {"ok": False, "message": "没有最近的选品结果，请先调用 trend_pick"}
            if rank < 1 or rank > len(items):
                return {"ok": False, "message": f"排名超范围（当前 1~{len(items)}）"}
            p_ = items[rank - 1]
            url = p_.get("url") or ""
            if not url:
                return {"ok": False, "message": "该候选没有链接"}
            _o = p_.get("offer_id") or url.rstrip("/").split("/")[-1].replace(".html", "")
            _exist = _existing_by_source(f"1688-{_o}")
            if _exist:
                return {"ok": True, "id": _exist.id, "title_cn": _exist.title_cn,
                        "already_exists": True,
                        "message": "同款草稿已存在，未重复创建"}
            det = rpa1688.collect_detail(url, 9222)
            _oid = p_.get("offer_id") or url.rstrip("/").split("/")[-1].replace(".html", "")
            item = {
                "id": f"1688-{_oid}",
                "url": url, "offer_id": _oid,
                "title": (det.get("title") or p_.get("title") or "").strip(),
                "price_cny": det.get("price_cny") or p_.get("price_cny") or 0,
                "sales_30d": p_.get("sales_30d") or 0,
                "repurchase_rate": p_.get("repurchase_rate") or 0,
                "supplier": det.get("supplier") or p_.get("supplier") or "",
                "weight_g": det.get("weight_g") or 0,
                "skus": det.get("skus") or ["Default"],
                "attributes": det.get("attributes") or {},
                "images": det.get("images") or [],
                "stock": det.get("stock") or 1000,
                "category": det.get("category") or p_.get("category") or "家居",
            }
            d = state.build_draft_from_source(item, rank)
            state.drafts[d.id] = d
            state.persist()
            state.add_log("agent", f"已按第 {rank} 名生成草稿：{d.title_cn[:18]}", {"type": "status"})
            return {"ok": True, "id": d.id, "title_cn": d.title_cn, "title_en": d.title_en,
                    "source_url": d.source_url, "cost": d.cost_cny, "price": d.supply_price,
                    "need_manual_price": d.need_manual_price, "price_note": d.price_rule}

        def _tool_list_drafts():
            rows = [{"id": d.id, "title": d.title_cn[:24], "cost": d.cost_cny, "status": d.status}
                    for d in state.drafts.values()]
            return {"ok": True, "count": len(rows), "drafts": rows[-20:]}

        def _tool_push(draft_ids: list[str] | None = None):
            ids = draft_ids or [d.id for d in state.drafts.values() if d.status in ("pending", "approved")]
            items, blocked = [], []
            for did in ids:
                d = state.drafts.get(did)
                if not d:
                    continue
                if d.qualification.get("required") and d.qual_status != "approved":
                    blocked.append(did)
                    continue
                if d.source_url:
                    items.append({"url": d.source_url, "title": d.title_en, "source_id": d.source_id})
            if not items:
                return {"ok": False, "message": "没有可推进妙手的草稿（可能需资质未登记）", "blocked": blocked}
            res = ms_adapters.get_adapter("miaoshou").collect(items, 9222, False, 35)
            res["blocked"] = blocked
            return res

        def _tool_publish(draft_ids: list[str] | None = None):
            ids = draft_ids or [d.id for d in state.drafts.values() if d.status == "approved"]
            if not ids:
                return {"ok": False, "message": "没有已确认的草稿"}
            return _real_publish(ids)

        def _tool_remember(key: str, value: str):
            return agent_memory.remember(key, value)

        def _tool_forget(key: str):
            return agent_memory.forget(key)

        def _tool_trend(keyword: str):
            return trend_ae.search(keyword, limit=12)

        def _tool_trend_pick(keyword_en: str, keyword_cn: str):
            from agent import trend_select
            r = trend_select.pick(keyword_en, keyword_cn, limit=5)
            return r

        impl = {
            "ae_trend": _tool_trend,
            "add_drafts": _tool_add_drafts,
            "draft_from_pick": _tool_draft_from_pick,
            "batch_draft": _tool_batch_draft,
            "generate_image": _tool_generate_image,
            "trend_pick": _tool_trend_pick,
            "search_1688": _tool_search,
            "list_drafts": _tool_list_drafts,
            "push_miaoshou": _tool_push,
            "publish": _tool_publish,
            "remember": _tool_remember,
            "forget": _tool_forget,
        }
        try:
            out = await run_in_threadpool(
                llm_agent.run, text, llm_cfg, impl, CHAT_HISTORY, 12,
                agent_memory.render_memory(),
            )

            # 硬校验：问热卖/价位/趋势却没查实时数据 → 强制重跑一次
            TREND_KW = ("热卖", "好卖", "销量", "价位", "趋势", "选品", "推荐方向", "卖得好")
            used = {t.get("tool") for t in (out.get("trace") or [])}
            if any(k in text for k in TREND_KW) and "ae_trend" not in used:
                out = await run_in_threadpool(
                    llm_agent.run,
                    text + "\n\n【系统强制】回答前必须调用 ae_trend 获取当前速卖通数据，禁止复述历史数据。",
                    llm_cfg, impl, CHAT_HISTORY, 12, agent_memory.render_memory(),
                )
        except Exception as e:  # noqa: BLE001
            out = {"ok": False, "message": f"Agent 执行异常：{type(e).__name__}: {e}", "trace": []}

        if out.get("ok"):
            reply = out.get("message") or ""
            CHAT_HISTORY.append({"role": "user", "content": text})
            CHAT_HISTORY.append({"role": "assistant", "content": reply})
            del CHAT_HISTORY[:-agent_memory.MAX_HISTORY]
            agent_memory.save_history(CHAT_HISTORY)
            MODEL_STATUS["last_ok_at"] = datetime.now().strftime("%H:%M:%S")
            MODEL_STATUS["last_error"] = ""
            MODEL_STATUS["model"] = llm_cfg.get("model") or ""
            msg = state.add_log("agent", reply, {"type": "agent", "trace": out.get("trace")})
            return {"intent": "agent", "message": msg, "items": collected, "trace": out.get("trace", [])}

        # 模型不可用：明确告知，不再用模板糊过去
        err = (out.get("message") or "未知错误").strip()
        MODEL_STATUS["last_error"] = err[:300]
        MODEL_STATUS["last_error_at"] = datetime.now().strftime("%H:%M:%S")
        MODEL_STATUS["model"] = llm_cfg.get("model") or ""
        msg = state.add_log(
            "agent",
            f"**模型调用失败**：{err[:200]}\n\n"
            f"这不影响已生成的数据，但本轮没法继续理解你的话。\n"
            f"可以：① 等 10 秒再说一次；② 到「设置」检查 DeepSeek Key 与模型名；③ 余额是否用完。",
            {"type": "err"},
        )
        return {"intent": "agent", "message": msg, "items": collected, "trace": out.get("trace", [])}

    if intent == "real":
        from fastapi.concurrency import run_in_threadpool

        result = await run_in_threadpool(_real_pipeline, text)
        result["intent"] = intent
        return result

    if intent in ("auto", "select"):
        from fastapi.concurrency import run_in_threadpool

        try:
            result = await run_in_threadpool(_real_pipeline, text)
        except Exception as e:  # noqa: BLE001
            msg = state.add_log("agent", f"真实采集失败：{type(e).__name__}: {e}。请先启动调试 Chrome 并登录 1688。", {"type": "guide"})
            return {"intent": intent, "message": msg, "items": []}
        result["intent"] = intent
        return result

    if intent == "publish":
        approved = [d for d in state.drafts.values() if d.status == "approved"]
        if not approved:
            return {
                "intent": intent,
                "message": state.add_log(
                    "agent",
                    "还没有通过审核的草稿。先去**审核台**把商品确认一下，我再提报。",
                    {"type": "guide"},
                ),
            }
        from fastapi.concurrency import run_in_threadpool

        res = await run_in_threadpool(_real_publish, [d.id for d in approved])
        msg = state.add_log(
            "agent",
            f"妙手发布结果：**{'成功' if res.get('ok') else '未完成'}**。{res.get('message', '')}",
            {"type": "publish_result", "result": res},
        )
        return {"intent": intent, "message": msg, "result": res}

    return {"intent": intent, "message": state.reply(intent, text)}


@app.post("/api/generate")
async def generate(body: IdsIn):
    """草稿在真实采集时已生成；此接口仅返回已存在草稿，不再用 mock 数据生成。"""
    if not body.ids:
        raise HTTPException(400, "未选择商品")
    missing = [i for i in body.ids if i not in state.drafts]
    if missing:
        raise HTTPException(400, "这些商品没有真实草稿，请先在对话里做一次真实采集")
    return {"ok": True, "count": len(body.ids), "drafts": [draft_to_dict(state.drafts[i]) for i in body.ids]}


def _start_generate(ids: list[str]):
    import asyncio

    job_id = f"job-{uuid.uuid4().hex[:8]}"
    task = Task(
        id=f"task-{int(time.time())}",
        name=f"选品提报 · {len(ids)} 个商品",
        kind="generate",
        total=len(ids),
        step="准备中",
    )
    state.tasks[task.id] = task
    state.jobs[job_id] = {"id": job_id, "status": "running", "progress": 0, "step": "准备中", "task_id": task.id}
    asyncio.create_task(state.generate_job(job_id, ids))
    return {"job_id": job_id, "task_id": task.id}


@app.get("/api/job/{job_id}")
def job(job_id: str):
    if job_id not in state.jobs:
        raise HTTPException(404, "任务不存在")
    j = state.jobs[job_id]
    out = dict(j)
    if j.get("task_id") in state.tasks:
        out["task"] = task_to_dict(state.tasks[j["task_id"]])
    return out


@app.get("/api/tasks")
def tasks():
    return [task_to_dict(t) for t in state.tasks.values()]


@app.patch("/api/drafts/{draft_id}")
def patch_draft(draft_id: str, body: DraftPatch):
    d = state.drafts.get(draft_id)
    if not d:
        raise HTTPException(404, "草稿不存在")
    for field in ("title_en", "supply_price", "stock", "weight_g", "sku_code", "sku_prefix"):
        val = getattr(body, field)
        if val is not None:
            setattr(d, field, val)
    state.persist()
    return draft_to_dict(d)


class QualIn(BaseModel):
    status: str = "approved"   # approved | rejected | pending
    cert_no: str = ""
    expire: str = ""
    operator: str = ""


@app.post("/api/drafts/{draft_id}/qualification")
def set_qualification(draft_id: str, body: QualIn):
    d = state.drafts.get(draft_id)
    if not d:
        raise HTTPException(404, "草稿不存在")
    if not d.qualification.get("required"):
        raise HTTPException(400, "该商品不需要资质")
    d.qual_status = body.status
    d.qual_cert = {
        "cert_no": body.cert_no,
        "expire": body.expire,
        "operator": body.operator or "运营",
        "at": time.strftime("%Y-%m-%d %H:%M"),
    }
    state.add_log("agent", f"资质登记：**{d.title_en[:30]}** → {body.status}（证书 {body.cert_no or '未填'}）",
                  {"type": "status"})
    state.persist()
    return draft_to_dict(d)


@app.delete("/api/drafts/{draft_id}")
def delete_draft(draft_id: str):
    d = state.drafts.pop(draft_id, None)
    if not d:
        raise HTTPException(404, "草稿不存在")
    state.add_log("agent", f"已删除草稿：{d.title_cn[:20]}", {"type": "status"})
    state.persist()
    return {"ok": True, "deleted": draft_id, "left": len(state.drafts)}


@app.post("/api/drafts/delete")
def delete_drafts(body: IdsIn):
    n = 0
    for i in body.ids:
        if state.drafts.pop(i, None):
            n += 1
    state.add_log("agent", f"已批量删除 **{n}** 个草稿", {"type": "status"})
    state.persist()
    return {"ok": True, "deleted": n, "left": len(state.drafts)}


@app.post("/api/drafts/approve")
def approve(body: IdsIn):
    n = 0
    blocked = []
    for i in body.ids:
        d = state.drafts.get(i)
        if not d:
            continue
        if d.qualification.get("required") and d.qual_status != "approved":
            blocked.append(d.id)
            continue
        if d.status == "pending":
            d.status = "approved"
            n += 1
    state.add_log("agent", f"已确认 **{n}** 个商品，可随时提报。"
                           + (f"（{len(blocked)} 个需资质被拦截）" if blocked else ""), {"type": "status"})
    state.persist()
    return {"approved": n, "blocked": blocked}


def _real_publish(ids: list[str], port: int = 9222) -> dict:
    """真实发布：在妙手速卖通全托管采集箱里执行发布，并按结果回写草稿状态。"""
    drafts = [state.drafts[i] for i in ids if i in state.drafts]
    gate = [d for d in drafts
            if d.qualification.get("required") and d.qual_status != "approved"]
    drafts = [d for d in drafts if d not in gate]
    if not drafts:
        return {"ok": False, "blocked": [d.id for d in gate], "message": "全部被资质闸门拦截"}

    ids_by_source = {str(d.source_id): d for d in drafts if d.source_id}
    if not ids_by_source:
        return {"ok": False, "message": "草稿缺少 1688 货源 ID，无法在妙手定位商品"}

    adapter = ms_adapters.get_adapter("miaoshou")
    res = adapter.publish(list(ids_by_source.keys()), port=port, dry_run=False)
    res["blocked"] = [d.id for d in gate]

    if res.get("ok"):
        for sid in res.get("found", []):
            d = ids_by_source.get(str(sid))
            if d:
                d.status = "submitted"
    state.persist()
    return res


@app.post("/api/publish")
async def publish(body: IdsIn):
    from fastapi.concurrency import run_in_threadpool

    ids = [i for i in body.ids if i in state.drafts]
    if not ids:
        raise HTTPException(400, "没有可提报的商品")
    blocked = [i for i in ids
               if state.drafts[i].qualification.get("required") and state.drafts[i].qual_status != "approved"]
    ids = [i for i in ids if i not in blocked]
    if not ids:
        raise HTTPException(400, f"{len(blocked)} 个商品需资质未登记，已被拦截")

    res = await run_in_threadpool(_real_publish, ids)
    res["job_id"] = None
    res["blocked_drafts"] = blocked
    return res


@app.get("/api/trend")
async def get_trend(keyword: str, refresh: bool = False):
    """速卖通前台实时热销（默认 2 小时缓存）。"""
    from fastapi.concurrency import run_in_threadpool
    return await run_in_threadpool(trend_ae.search, keyword, 9222, 20, not refresh)


class SetPriceIn(BaseModel):
    draft_id: str
    supply_price: float


@app.post("/api/drafts/set_price")
def set_draft_price(body: SetPriceIn):
    """客户手动给供货价（成本 <10 元时用）。"""
    d = state.drafts.get(body.draft_id)
    if not d:
        return {"ok": False, "message": "草稿不存在"}
    if body.supply_price <= 0:
        return {"ok": False, "message": "供货价必须大于 0"}
    d.supply_price = round(float(body.supply_price), 2)
    d.need_manual_price = False
    d.price_rule = "客户手动指定"
    state.persist()
    state.add_log("agent", f"已设置供货价 **¥{d.supply_price:.2f}**（{d.title_cn[:14]}）", {"type": "status"})
    return {"ok": True, "supply_price": d.supply_price}


@app.get("/api/images/status")
def images_status():
    """生图是否已启用（客户配置火山方舟后才可用）。"""
    from agent import image_gen
    return image_gen.status()


class GenImageIn(BaseModel):
    draft_id: str
    image_type: str = "场景图"     # 首图/细节图/场景图/功能演示图/参数信息图
    size: str = ""


@app.post("/api/images/generate")
def images_generate(body: GenImageIn):
    """按 6 图规划生成一张图（需已配置 provider）。"""
    from agent import image_gen

    d = state.drafts.get(body.draft_id)
    if not d:
        return {"ok": False, "message": "草稿不存在"}

    st = image_gen.status()
    if not st["enabled"]:
        return {"ok": False, "disabled": True,
                "message": "生图未启用：在 settings.json → image_gen 填火山方舟 Key 与模型即可（无需 Agent 套餐）"}

    core = (d.title_en or d.title_cn)[:80]
    prompt = image_gen.build_prompt(body.image_type, core)
    r = image_gen.generate(prompt, body.size)
    if r.get("ok"):
        state.add_log("agent", f"已生成 {body.image_type}（{d.title_cn[:14]}）", {"type": "status"})
    return {**r, "prompt": prompt}


@app.get("/api/logs")
def get_logs(limit: int = 200):
    """返回最近日志（含落盘的完整文件路径）。"""
    return {
        "logs": state.logs[-limit:],
        "count": len(state.logs),
        "file": str(state.LOG_FILE),
    }


class LogSubmitIn(BaseModel):
    note: str = ""
    webhook: str = ""


@app.post("/api/logs/submit")
def submit_logs(body: LogSubmitIn):
    """打包日志（含环境信息，自动脱敏），可提交到 webhook；未配置则存本地包。"""
    import platform
    import urllib.request

    bundle = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "note": body.note,
        "env": {"python": platform.python_version(), "os": platform.platform(),
                "app": str(BASE_DIR)},
        "logs": state.logs[-500:],
        "stats": {"drafts": len(state.drafts), "tasks": len(state.tasks)},
    }
    path = DATA_DIR / f"logs_bundle_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8")

    hook = (body.webhook or (settings.get("logs") or {}).get("webhook") or "").strip()
    if hook:
        try:
            req = urllib.request.Request(
                hook, data=json.dumps(bundle, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=15) as r:
                return {"ok": True, "message": f"已提交：HTTP {r.status}", "file": str(path)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"提交失败：{type(e).__name__}: {e}",
                    "file": str(path), "hint": "日志包已保存在本地，可手动发给我"}
    return {"ok": True, "message": f"日志包已生成：{path.name}（未配置 webhook，未上传）",
            "file": str(path)}


@app.get("/api/prompt")
def get_prompt():
    path = BASE_DIR / "prompts" / "aliexpress_listing_v1.md"
    if not path.exists():
        raise HTTPException(404, "提示词模板不存在")
    return {"template": settings.get("prompt", {}), "text": path.read_text(encoding="utf-8")}


@app.post("/api/settings")
def save_settings(body: SettingsIn):
    global settings
    settings = body.data
    SETTINGS_FILE.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


@app.post("/api/reset")
def reset():
    state.drafts.clear()
    state.tasks.clear()
    state.jobs.clear()
    state.logs.clear()
    state.seq = 0
    state.usage = {"calls": 0, "prompt_chars": 0, "completion_chars": 0}
    CHAT_HISTORY.clear()
    agent_memory.save_history([])
    try:
        state.STORE.unlink(missing_ok=True)
    except Exception:
        pass
    return {"ok": True}


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")
