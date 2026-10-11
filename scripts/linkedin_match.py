#!/usr/bin/env python3
"""人名 → 领英主页 匹配器（零成本 DIY 路线）

思路（二段式消歧）：`site:linkedin.com/in "<姓名>" "<公司/机构>"`，
再用"公司词是否出现在摘要里 + slug 是否就是姓名"两层规则给置信度打分。

设计原则：
- **宁缺勿错**：置信度不够就给"搜索链接"，绝不硬塞一个可能错的人。
- 只输出结果供人点击，**不做自动关注/自动连接**（有账号风险，且是用户的动作）。

用法（在 Hermes 的 execute_code / agent 里调用；依赖 hermes_tools.web_search）：
    from linkedin_match import match_many
    rows = match_many([("Yann LeCun", "AMI Labs"), ...])

CLI（离线打印，不联网）：
    python3 linkedin_match.py --show-rule
"""
from __future__ import annotations

import re
import urllib.parse

__all__ = ["match_one", "match_many", "search_url", "render_links_line"]


def search_url(name: str, org: str = "") -> str:
    """兜底：领英站内搜索链接（永远可用，不依赖任何 API）。"""
    q = f"{name} {org}".strip()
    return f"https://www.linkedin.com/search/results/people/?keywords={urllib.parse.quote_plus(q)}"


def _slug(url: str) -> str:
    m = re.search(r"linkedin\.com/in/([^/?#]+)", url, re.I)
    return m.group(1).lower() if m else ""


def _name_tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[\s\-_.]+", name.lower()) if len(t) > 1]


def _score(cand: dict, org: str, first: bool, name: str) -> tuple[int, list[str]]:
    """给候选打分：越高越可信。返回 (分数, 理由列表)。"""
    score, why = 0, []
    slug = _slug(cand.get("url", ""))
    blob = f"{cand.get('title','')} {cand.get('desc','')}".lower()

    # ① 公司/机构词出现在摘要或标题里 —— 这是消歧的关键证据
    org_tokens = [t for t in re.split(r"[\s\-_.]+", org.lower()) if len(t) > 2]
    if org_tokens and any(t in blob for t in org_tokens):
        score += 3
        why.append("摘要含机构名")
    # ② slug 就是"姓名本身"（如 yann-lecun）——最干净
    toks = _name_tokens(name)
    if toks and all(t in slug for t in toks[:2]) and len(slug) <= len("".join(toks)) + 4:
        score += 2
        why.append("slug 即姓名")
    # ③ 首条结果
    if first:
        score += 1
        why.append("搜索首条")
    # ④ slug 与姓名毫无关系 → 减分（多半是搜索引擎塞的无关人）
    if toks and not any(t in slug for t in toks):
        score -= 3
        why.append("slug 与姓名无关")
    return score, why


def match_one(web_search, name: str, org: str = "", limit: int = 5) -> dict:
    """返回 {best, confidence, reason, candidates}；confidence ∈ 高/中/低。"""
    query = f'site:linkedin.com/in "{name}"' + (f' "{org}"' if org else "")
    out = {"name": name, "org": org, "query": query, "best": "", "confidence": "低",
           "reason": "", "candidates": []}
    try:
        res = web_search(query, limit=limit)
    except Exception as e:  # noqa: BLE001
        out["reason"] = f"搜索失败:{type(e).__name__}"
        return out

    cands = []
    for h in res.get("data", {}).get("web", []):
        u = h.get("url", "")
        if "linkedin.com/in/" in u:
            cands.append({"url": u, "title": h.get("title", ""), "desc": h.get("description", "")})
    out["candidates"] = cands
    if not cands:
        out["reason"] = "无 /in/ 命中"
        return out

    scored = []
    for i, c in enumerate(cands):
        sc, why = _score(c, org, i == 0, name)
        scored.append((sc, why, c))
    scored.sort(key=lambda x: -x[0])
    sc, why, best = scored[0]
    out["best"] = best["url"]
    out["confidence"] = "高" if sc >= 4 else ("中" if sc == 3 else "低")
    out["reason"] = "＋".join(why) or "证据不足"
    if out["confidence"] == "低":
        out["best"] = ""          # 宁缺勿错：低置信度不给个人主页
    return out


def match_many(pairs, web_search=None, sleep: float = 0.0) -> list[dict]:
    if web_search is None:
        from hermes_tools import web_search as _ws  # 仅在 Hermes 运行时可用
        web_search = _ws
    rows = []
    for name, org in pairs:
        rows.append(match_one(web_search, name, org))
        if sleep:
            import time
            time.sleep(sleep)
    return rows


def render_links_line(row: dict) -> str:
    """生成卡片里那一行「关注入口」。高/中置信度给个人主页，否则给搜索链接。"""
    name, org = row["name"], row.get("org", "")
    li = row.get("best") or search_url(name, org)
    tag = {"高": "", "中": "（待核）", "低": ""}[row.get("confidence", "低")]
    return f"- **关注入口**：LinkedIn → <{li}>{tag} ｜ 搜索兜底 → <{search_url(name, org)}>"


if __name__ == "__main__":
    import sys

    if "--show-rule" in sys.argv:
        print(__doc__)
        print("打分规则：摘要含机构名 +3｜slug 即姓名 +2｜搜索首条 +1｜slug 与姓名无关 -3")
        print("≥4 → 高（给个人主页）｜=3 → 中（给主页但标待核）｜<3 → 低（只给搜索链接）")
