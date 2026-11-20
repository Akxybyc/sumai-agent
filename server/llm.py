"""算力接入层（LLM Provider Adapter）。

设计目标：
- 多供应商可插拔：火山方舟 / 阿里百炼 / 腾讯混元 / DeepSeek / 智谱 / Kimi / OpenAI / 本地 Ollama / 自定义网关
- 统一走 OpenAI 兼容协议（绝大多数厂商都提供 /chat/completions）
- 非兼容协议（如运营商 Agent 平台的 AK/SK 签名）通过 `auth` 扩展点适配
- 支持主模型 + 备用模型链，按任务分配模型（文案 / 类目 / 视觉）
- 用量与费用估算，便于客户按量控成本
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

PROVIDERS = [
    {
        "id": "volcengine",
        "name": "火山引擎 · 方舟（豆包）",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["doubao-seed-1-6-250615", "doubao-1-5-pro-32k-250115"],
        "auth": "bearer",
        "note": "OpenAI 兼容，需在方舟控制台开通推理接入点",
    },
    {
        "id": "dashscope",
        "name": "阿里云 · 百炼（通义千问）",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-plus", "qwen-max", "qwen-vl-max"],
        "auth": "bearer",
        "note": "OpenAI 兼容模式",
    },
    {
        "id": "hunyuan",
        "name": "腾讯云 · 混元",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "models": ["hunyuan-turbos-latest", "hunyuan-vision"],
        "auth": "bearer",
        "note": "OpenAI 兼容",
    },
    {
        "id": "deepseek",
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "auth": "bearer",
        "note": "性价比高，适合大批量文案生成",
    },
    {
        "id": "zhipu",
        "name": "智谱 · GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4-plus", "glm-4v-plus"],
        "auth": "bearer",
        "note": "GLM-4V 可用于主图理解",
    },
    {
        "id": "moonshot",
        "name": "月之暗面 · Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-32k", "kimi-k2-0711-preview"],
        "auth": "bearer",
        "note": "长文本能力强",
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o-mini", "gpt-4o"],
        "auth": "bearer",
        "note": "需海外网络环境",
    },
    {
        "id": "siliconflow",
        "name": "硅基流动 SiliconFlow",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"],
        "auth": "bearer",
        "note": "多模型聚合，按 token 计费",
    },
    {
        "id": "ollama",
        "name": "本地 Ollama / vLLM",
        "base_url": "http://127.0.0.1:11434/v1",
        "models": ["qwen2.5:14b", "llama3.1:8b"],
        "auth": "none",
        "note": "本地推理，零 API 成本，需显卡",
    },
    {
        "id": "custom",
        "name": "自定义 · 运营商 Agent 平台 / 私有网关",
        "base_url": "",
        "models": [],
        "auth": "custom",
        "note": "填 OpenAI 兼容地址；AK/SK 签名类平台可在 auth 扩展点适配",
    },
]

TASKS = [
    {"id": "copy", "name": "文案生成", "desc": "标题 / 简介 / 卖点"},
    {"id": "vision", "name": "图片理解", "desc": "主图卖点识别、白底检测"},
    {"id": "category", "name": "类目匹配", "desc": "类目与属性映射"},
]

# 粗略单价（元 / 千 token），仅用于成本预估，可在设置里覆盖
PRICE_TABLE = {
    "doubao-seed-1-6-250615": 0.0008,
    "qwen-plus": 0.0008,
    "deepseek-chat": 0.001,
    "glm-4-plus": 0.005,
    "moonshot-v1-32k": 0.012,
    "gpt-4o-mini": 0.0011,
    "default": 0.002,
}


def get_provider(pid: str) -> dict:
    for p in PROVIDERS:
        if p["id"] == pid:
            return p
    return PROVIDERS[-1]


def estimate_cost(model: str, prompt_chars: int, completion_chars: int) -> float:
    price = PRICE_TABLE.get(model, PRICE_TABLE["default"])
    # 粗略换算：英文约 4 字符 / token，中文约 1.5 字符 / token，统一按 3 字符估
    tokens = (prompt_chars + completion_chars) / 3
    return round(tokens / 1000 * price, 4)


def test_connection(cfg: dict) -> dict:
    """连通性测试。未填 Key 时返回演示态结果，不发真实请求。"""
    provider = get_provider(cfg.get("provider", "custom"))
    base_url = (cfg.get("base_url") or provider["base_url"]).rstrip("/")
    model = cfg.get("model") or (provider["models"][0] if provider["models"] else "")
    api_key = cfg.get("api_key") or ""

    if provider["auth"] == "none":
        return {"ok": True, "mode": "local", "message": f"本地推理端点：{base_url}（未发请求）"}

    if not api_key:
        return {
            "ok": False,
            "mode": "mock",
            "message": "未填写 API Key。当前为演示态，生成走 Mock；填入 Key 后可测试真实连接。",
        }

    if not base_url:
        return {"ok": False, "mode": "config", "message": "未填写 Base URL"}

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1,
        "stream": False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        ms = int((time.time() - start) * 1000)
        model_echo = body.get("model", model)
        return {"ok": True, "mode": "live", "message": f"连接成功 · {model_echo} · {ms}ms"}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:200]
        return {"ok": False, "mode": "live", "message": f"HTTP {e.code}：{detail}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "mode": "live", "message": f"连接失败：{type(e).__name__} {e}"}
