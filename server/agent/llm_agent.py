"""LLM 主导的 Agent 循环（OpenAI 兼容 / DeepSeek Function Calling）。

设计：
- 模型自己判断用户意图：闲聊/追问类目/调用工具
- 工具全部是真实动作（1688 采集、妙手推送、妙手发布）
- 最多 4 轮工具调用；每轮把真实结果回灌给模型
- 不写死关键词：关键词只能由模型从用户话里得出，或者由模型反问用户
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

SYSTEM = """你是「上品助手」，服务速卖通全托管卖家的跨境上品 Agent。

你的工作方式：
1. 先理解意图，再决定是否调用工具。用户没给具体品类时**不要**搜索。
2. 结合对话历史理解省略和口误：例如上一轮在聊“热卖的品”，用户只回一个“品”，你要按上下文理解为“热卖的品”，不要当成新话题。
3. 缺品类时只反问问一句，**不要每次都罗列同一串示例**。若上一轮已经举过例子，这轮就直接问一句“哪个品类？”，不要重复清单。
4. 用户给了品类就调用 search_1688。若用户提过“不要资质/免资质”，把 no_qualification 设为 true。
5. 采集完成后用真实数据概括（多少条、选了哪几个、价格、销量），并提示去审核台确认。不要逐字套模板，按实际数据说。
6. 只有用户明确说“推妙手/采集箱”才调 push_miaoshou；明确说“发布/上架”才调 publish。
7. 工具失败（未连接浏览器、滑块等）如实转述，不编造数据。
8. 同一轮不要重复调用同一个工具。
9. 用户说“随便/你定/不知道才问你/给我个方向”时，**不要再反问**：自己选一个免资质、需求稳定的方向（收纳盒、手机支架、宠物梳、桌面收纳之类），直接调 search_1688，并在回复第一句说明“我替你选的是 XX，因为…”。

10. **选品必须查实时数据**：用户问“最近什么好卖/推荐方向/这个品类怎么样”时，先调 ae_trend 拿速卖通前台最新数据，
    回复里必须写明“数据时间（抓取时间）”，并基于销量/价格带给结论；禁止凭记忆或猜。
    即使上一轮刚查过，也要重新调用一次（可用缓存），不得复述历史里的数字。
    **客户要多条（≥2 条）时，优先用 batch_draft 一次建完**，不要逐个 draft_from_pick 浪费轮次。
    要给"具体推荐哪几款"时，必须调 trend_pick（趋势 + 1688 货源 + 毛利），不能只调 ae_trend 就下结论。
13. **供货价规则（硬性）**：成本 ≥10 元 = (原价 + 国内运费 + 5 元打包费) × 2，由系统自动算好，直接报给客户；
    **生图**：只有客户明确要图才调 generate_image（传 draft_id + 类型），不要主动生成；系统未配生图会返回未启用，如实告知不要假装。
    成本 <10 元时，**绝不自己定价**，必须明确问客户"这款成本 X 元，你想定多少供货价？"，等客户回答后用 set_price 逻辑写入。
    汇报价格时把公式一起写出来，例如 "(12.00 + 0 + 5) × 2 = 34.00"。
11. 用户表达长期偏好或业务规则（如“以后只做免资质”“价格别超过 50”“XX 类目别碰”）时，调用 remember 记下来，并用一句话确认。
12. 记忆里已有明确规则时直接遵守，不要重复问。

风格：中文、口语、简短。不要客套，不要“好的我马上为您…”，不要承诺没发生的结果。
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_1688",
            "description": "在 1688 真实搜索指定类目并生成待审核草稿。仅在用户给出具体品类时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "类目关键词，如 瑜伽垫、收纳盒、手机支架"},
                    "limit": {"type": "integer", "description": "生成草稿数量，默认 3"},
                    "no_qualification": {"type": "boolean", "description": "true 表示排除需要资质的类目"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ae_trend",
            "description": "查速卖通前台实时热销（标题/价格/销量/抓取时间）。回答热卖、趋势、选品方向前必须调用，不要凭记忆。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "英文关键词，如 storage box"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trend_pick",
            "description": "趋势选品：先查速卖通实时价格带，再按目标成本去 1688 找货源并打分排序。给出选品建议时必须用它。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword_en": {"type": "string", "description": "速卖通英文关键词，如 car phone holder"},
                    "keyword_cn": {"type": "string", "description": "1688 中文关键词，如 车载手机支架"},
                },
                "required": ["keyword_en", "keyword_cn"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "按 6 图规划给某个草稿生成一张图（场景图/功能演示图/参数信息图/细节图/首图）。只传类型，厂商由系统配置决定。",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "草稿 ID"},
                    "image_type": {"type": "string",
                                   "description": "首图/细节图/场景图/功能演示图/参数信息图"},
                },
                "required": ["draft_id", "image_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "batch_draft",
            "description": "批量选品并建草稿：一次调用完成「趋势选品 → 取前 N 名 → 生成草稿」，客户要多条时优先用这个，省轮次。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword_en": {"type": "string", "description": "速卖通英文关键词"},
                    "keyword_cn": {"type": "string", "description": "1688 中文关键词"},
                    "count": {"type": "integer", "description": "要建几条草稿（1~20）"},
                },
                "required": ["keyword_en", "keyword_cn", "count"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_from_pick",
            "description": "把最近一次 trend_pick 结果里的第 N 名直接生成草稿（推荐用这个，避免手工拼链接）",
            "parameters": {
                "type": "object",
                "properties": {"rank": {"type": "integer", "description": "排名，从 1 开始"}},
                "required": ["rank"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_drafts",
            "description": "把指定的 1688 商品链接生成草稿（用户确认选品后使用）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {"type": "array", "items": {"type": "string"},
                             "description": "1688 商品链接，如 http://detail.1688.com/offer/xxx.html"},
                },
                "required": ["urls"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_drafts",
            "description": "查看当前草稿列表（ID、标题、成本价、状态）。",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "push_miaoshou",
            "description": "把草稿推进妙手：1688 链接采集 + 自动认领到速卖通全托管采集箱。",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_ids": {"type": "array", "items": {"type": "string"},
                                  "description": "草稿 ID 列表；留空表示全部已确认或待审核草稿"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "记住用户的长期偏好或业务事实（跨会话生效）。例如：只做免资质类目、价格带上限、禁做类目、目标店铺。",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "简短键名，如 资质偏好 / 价格带上限"},
                    "value": {"type": "string", "description": "具体内容，如 只做免资质类目"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "forget",
            "description": "删除一条不再适用的长期记忆。",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish",
            "description": "在妙手速卖通全托管采集箱里发布草稿对应的商品。",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_ids": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
]


def _post(cfg: dict, payload: dict, timeout: int = 90) -> dict:
    base = (cfg.get("base_url") or "https://api.deepseek.com/v1").rstrip("/")
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.get('api_key', '')}",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def run(user_text: str, cfg: dict, tool_impl: dict, history: list[dict] | None = None,
        max_rounds: int = 12, memory_text: str = "") -> dict:
    """执行一轮 Agent 对话。tool_impl: {name: callable}"""
    if not cfg.get("api_key"):
        return {"ok": False, "message": "未配置大模型 API Key，无法用模型主导。请到设置里填写。"}

    sys_prompt = SYSTEM
    if memory_text:
        sys_prompt += "\n\n已知长期记忆（用户偏好/业务事实，回答时要遵守）：\n" + memory_text
    msgs = [{"role": "system", "content": sys_prompt}]
    if history:
        msgs.extend(history[-6:])
    msgs.append({"role": "user", "content": user_text})

    trace: list[dict] = []
    for _ in range(max_rounds):
        payload = {
            "model": cfg.get("model") or "deepseek-chat",
            "messages": msgs,
            "tools": TOOLS,
            "tool_choice": "auto",
            "temperature": 0.3,
        }
        try:
            data = _post(cfg, payload)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:300]
            # 主模型不支持 tools/multimodal 时，自动退回 deepseek-chat 重试一次
            if e.code in (400, 404) and (cfg.get("model") or "") != "deepseek-chat":
                fallback = dict(cfg)
                fallback["model"] = "deepseek-chat"
                payload["model"] = "deepseek-chat"
                try:
                    data = _post(fallback, payload)
                except Exception as e2:  # noqa: BLE001
                    return {"ok": False,
                            "message": f"模型调用失败（已尝试兜底）：{type(e2).__name__}", "trace": trace}
            else:
                return {"ok": False, "message": f"模型调用失败 HTTP {e.code}: {body}", "trace": trace}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": f"模型调用失败：{type(e).__name__}: {e}", "trace": trace}

        msg = (data.get("choices") or [{}])[0].get("message") or {}
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"ok": True, "message": msg.get("content") or "", "trace": trace}

        msgs.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for c in calls:
            name = c["function"]["name"]
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            fn = tool_impl.get(name)
            if not fn:
                result = {"ok": False, "message": f"未知工具 {name}"}
            else:
                try:
                    result = fn(**args)
                except TypeError:
                    result = fn()
                except Exception as e:  # noqa: BLE001
                    result = {"ok": False, "message": f"{type(e).__name__}: {e}"}
            trace.append({"tool": name, "args": args, "result_ok": bool(result.get("ok")),
                          "message": str(result.get("message", ""))[:200]})
            msgs.append({
                "role": "tool",
                "tool_call_id": c.get("id", ""),
                "content": json.dumps(result, ensure_ascii=False)[:4000],
            })

    # 轮数用尽：强制模型做一次不带工具的总结，避免只回一句占位话
    try:
        msgs.append({"role": "user",
                     "content": "工具调用轮数已用尽。请直接用文字总结：已完成的动作、建了哪些草稿（标题+价格）、还差什么。"})
        data = _post(cfg, {"model": cfg.get("model") or "deepseek-chat", "messages": msgs,
                           "temperature": 0.3, "tool_choice": "none"})
        msg = (data.get("choices") or [{}])[0].get("message") or {}
        content = (msg.get("content") or "").strip()
        return {"ok": True, "message": content or "（本轮未产出结果，请重试一次）", "trace": trace}
    except Exception:  # noqa: BLE001
        return {"ok": True, "message": "（已达工具调用轮数上限，请把结果直接告诉用户）", "trace": trace}
