"""生图能力（可插拔）：默认关闭，客户配置火山方舟后自动启用。

支持的 provider：
- volcano ：火山方舟 Seedream（推荐，国内直连）
- none    ：未配置

配置位置：data/settings.json → image_gen
{
  "provider": "volcano",
  "api_key": "xxxx",
  "base_url": "https://ark.cn-beijing.volces.com/api/v3",
  "model": "doubao-seedream-3-0-t2i-250415",
  "size": "1024x1024"
}
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


def _cfg() -> dict:
    try:
        s = json.loads((DATA / "settings.json").read_text(encoding="utf-8"))
        return s.get("image_gen") or {}
    except Exception:
        return {}


PRIORITY = ["volcano"]   # 未来可加 ali / jimeng / sd_web


def active_provider() -> str:
    """按优先级返回第一个可用的 provider（有 key 才算可用）。"""
    c = _cfg()
    chains = c.get("providers") or {}
    for name in PRIORITY:
        cfg = chains.get(name) or (c if (c.get("provider") or "") == name else {})
        if cfg.get("api_key"):
            return name
    # 兼容单 provider 配置
    if (c.get("provider") in PRIORITY) and c.get("api_key"):
        return c["provider"]
    return "none"


def status() -> dict:
    c = _cfg()
    name = active_provider()
    chain = c.get("providers") or {}
    cfg = chain.get(name) or c
    return {"enabled": name != "none", "provider": name,
            "model": cfg.get("model") or "", "size": cfg.get("size") or "1024x1024",
            "priority": PRIORITY,
            "message": f"生图已启用（{name}）" if name != "none"
                       else "未配置生图：填任一生图 provider 的 Key 即可，无需 Agent 套餐"}


def generate(prompt: str, size: str = "", timeout: int = 120) -> dict:
    c = _cfg()
    provider = active_provider()
    if provider == "none":
        return {"ok": False, "disabled": True,
                "message": "未启用生图：请在配置里填生图 provider 的 Key（火山方舟 Seedream 等），无需 Agent 套餐"}
    cfg = (c.get("providers") or {}).get(provider) or c

    if provider != "volcano":
        return {"ok": False, "message": f"暂不支持的生图 provider：{provider}"}

    base = (cfg.get("base_url") or c.get("base_url")
            or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
    body = {
        "model": cfg.get("model") or c.get("model") or "doubao-seedream-3-0-t2i-250415",
        "prompt": prompt,
        "size": size or cfg.get("size") or c.get("size") or "1024x1024",
        "response_format": "url",
        "watermark": False,
    }
    req = urllib.request.Request(
        base + "/images/generations",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['api_key']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
        items = data.get("data") or []
        url = (items[0] or {}).get("url") if items else ""
        return {"ok": bool(url), "url": url, "provider": "volcano",
                "message": "生成成功" if url else "接口未返回图片地址"}
    except urllib.error.HTTPError as e:
        txt = e.read().decode("utf-8", "ignore")[:300]
        return {"ok": False, "message": f"HTTP {e.code}: {txt}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "message": f"{type(e).__name__}: {e}"}


# 6 张图规划 → 生图 prompt（场景图/功能图/参数图可直接生成；产品图建议用实拍）
PROMPT_TPL = {
    "场景图": "Product scene photo, {product}, placed in a {scene} setting, natural light, "
              "lifestyle e-commerce photography, clean composition, 45 degree angle, no text",
    "功能演示图": "Product demonstration photo, {product} in use, hands interacting, "
                  "showing key function {feature}, bright studio lighting, no text",
    "参数信息图": "Clean product infographic layout, {product} on white background with "
                  "measurement arrows, minimal labels area, professional e-commerce style",
    "细节图": "Macro close-up detail shot of {product}, showing material texture {feature}, "
              "shallow depth of field, white background",
    "首图": "Main product image, {product}, pure white background, centered, "
            "professional e-commerce photography, soft shadow, no text",
}


def build_prompt(image_type: str, product_en: str, feature: str = "", scene: str = "modern home") -> str:
    tpl = PROMPT_TPL.get(image_type) or PROMPT_TPL["首图"]
    return tpl.format(product=product_en, feature=feature or "durable build", scene=scene)


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False))
    print(build_prompt("场景图", "stainless steel spice rack", scene="kitchen counter"))
