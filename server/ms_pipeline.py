"""一键流水线：草稿 → 采集进妙手 → 用「提示词规则生成的英文标题」+ 翻译后的描述/颜色名写入采集箱。

标题来源：草稿的 title_en（由 content.build_title_v2 按用户提示词生成：核心+属性+核心+长尾+流量、
115 个字母、无标点、实词大写）
描述/属性：妙手文本翻译（免费，不占图片额度）
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import ms_api

DATA = Path(__file__).resolve().parent.parent / "data"


def _clamp_stock(v) -> int:
    try:
        return max(0, min(int(v or 1000), 99999))
    except Exception:
        return 1000


def run(drafts: list[dict], dry_run: bool = False, log=print) -> dict:
    """drafts: [{id, source_url/url, title_en, price_cny}]"""
    todo = [d for d in drafts if (d.get("url") or d.get("source_url"))]
    if not todo:
        return {"ok": False, "message": "没有可采集的草稿（缺链接）"}

    # 草稿里已记录 detailId 的，直接复用，不重复采集
    existing = {}
    links = []
    for d in todo:
        u = d.get("url") or d.get("source_url")
        offer = u.rstrip("/").split("/")[-1].replace(".html", "")
        did0 = int(d.get("detail_id") or 0)
        if did0 > 0:
            existing[offer] = did0
        elif u and u not in links:
            links.append(u)
    log(f"复用已有 {len(existing)} 条，需新采 {len(links)} 条")

    mapping = dict(existing)
    if links:
        log(f"采集 {len(links)} 条链接…")
        r = ms_api.collect_by_links(links)
        if not r.get("ok"):
            return {"ok": False, "message": f"采集失败：{r.get('message')}"}
        mapping.update(((r.get("data") or {}).get("data") or {}).get("sourceItemIdAndDetailIdMap") or {})
        log(f"采集映射 {len(mapping)} 条（详情异步生成，稍后轮询）")
    else:
        log("全部已在箱内，跳过采集")

    # 等采集落库
    detail_by_offer = {}
    for _ in range(12):
        time.sleep(4)
        q = ms_api.list_collect_box(1, 100, "all")
        lst = ((q.get("data") or {}).get("data") or {}).get("detailList") or []
        for it in lst:
            for k in ("sourceItemId", "offerId", "sourceId"):
                sid = it.get(k)
                if sid and str(sid) in mapping:
                    detail_by_offer[str(sid)] = it.get("commonCollectBoxDetailId")
        if len(detail_by_offer) >= len(mapping):
            break

    done, failed, rows = 0, [], []
    for d in todo:
        url = d.get("url") or d.get("source_url")
        offer = url.rstrip("/").split("/")[-1].replace(".html", "")
        did = int(d.get("detail_id") or 0) or mapping.get(offer) or detail_by_offer.get(offer)
        if not did:
            failed.append({"draft": d.get("id"), "msg": "没拿到 detailId"})
            continue
        if dry_run:
            rows.append({"draft": d.get("id"), "detailId": did, "title": (d.get("title_en") or "")[:60]})
            done += 1
            continue
        try:
            # 采集是异步的：详情可能还没生成，轮询等 ossMd5 出现
            data, det, md5 = {}, {}, None
            for _try in range(8):
                q = ms_api.call(
                    "/open/v1/product/common_collect_box/common_collect_box/get_common_collect_box_detail",
                    {"commonCollectBoxDetailId": did})
                data = (q.get("data") or {}).get("data") or {}
                det = data.get("editCommonCollectBoxDetail") or {}
                md5 = data.get("ossMd5")
                if md5 and (det.get("title") or "").strip():
                    break
                time.sleep(3)
            if not md5:
                failed.append({"draft": d.get("id"), "msg": "详情未就绪（缺 ossMd5），请稍后重试"})
                continue

            # 标题：用提示词规则生成的英文（不是直译）
            title_en = (d.get("title_en") or "").strip()
            if not title_en:
                mp = ms_api.translate_strings([det.get("title") or ""]).get("map") or {}
                title_en = mp.get(det.get("title") or "") or (det.get("title") or "")

            fields = {
                "title": title_en[:250],
                "price": det.get("price") or d.get("price_cny") or 1,
                "stock": _clamp_stock(det.get("stock")),
                "colorPropName": "Color",
            }
            notes = det.get("notesText")
            if notes:
                mp2 = ms_api.translate_strings([notes]).get("map") or {}
                fields["notesText"] = (mp2.get(notes) or notes)[:60000]

            w = ms_api.edit_collect_box_item(did, fields, md5)
            if w.get("ok"):
                done += 1
                rows.append({"draft": d.get("id"), "detailId": did, "title": title_en[:60]})
            else:
                failed.append({"draft": d.get("id"),
                               "msg": (w.get("data") or {}).get("message") or w.get("message")})
        except Exception as e:  # noqa: BLE001
            failed.append({"draft": d.get("id"), "msg": f"{type(e).__name__}: {e}"})

    return {"ok": done > 0, "collected": len(mapping), "done": done,
            "failed": failed[:5], "items": rows,
            "dry_run": dry_run,
            "message": f"{'预演' if dry_run else '完成'}：采集 {len(mapping)} 条，写入英文 {done} 条"
                       + (f"，失败 {len(failed)} 条" if failed else "")}
