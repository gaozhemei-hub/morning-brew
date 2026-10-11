#!/usr/bin/env python3
"""新赛道探针：GitHub 星标最多的项目 → README 结构 → 架构图线索。

对应经验贴的复用动作③：「遇到一个新赛道，先去 GitHub 搜 Star 最多的开源项目，
看它的 README.md 和 Architecture Diagram（架构图）。」

用法：
    python3 repo_probe.py "agent memory"            # 默认取前 5 个仓库
    python3 repo_probe.py "ai video generation" -n 3 --readme-chars 3000
输出：Markdown 片段，直接可贴进深挖笔记。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

PROXY = os.environ.get("HERMES_PROXY", "http://127.0.0.1:7890")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/125 Safari/537.36"
ARCH_HINT = re.compile(
    r"(architecture|arch\.|overview|design|how-it-works|workflow|diagram|system[-_]?design)", re.I)
IMG_RX = re.compile(r"!\[[^\]]*\]\(([^)\s]+)\)")
IMG_HTML_RX = re.compile(r'<img[^>]+src="([^"]+)"', re.I)


def http_json(url: str, timeout: int = 30):
    for proxy in (False, True):  # 直连优先，失败走代理
        try:
            handlers = [urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})] if proxy else []
            opener = urllib.request.build_opener(*handlers)
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
            with opener.open(req, timeout=timeout) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1)
    raise last  # type: ignore[misc]


def search_repos(topic: str, n: int) -> list[dict]:
    q = urllib.parse.quote(topic)
    data = http_json(f"https://api.github.com/search/repositories?q={q}&sort=stars&order=desc&per_page={n}")
    out = []
    for it in data.get("items", []):
        out.append({
            "full_name": it["full_name"],
            "stars": it["stargazers_count"],
            "desc": it.get("description") or "",
            "lang": it.get("language") or "",
            "pushed": (it.get("pushed_at") or "")[:10],
            "topics": it.get("topics") or [],
            "url": it["html_url"],
        })
    return out


def readme_of(full_name: str, limit: int) -> tuple[str, str]:
    """取 README：API → raw(main) → raw(master)。API 对超大文件不返回 content，所以必须有 raw 兜底。"""
    errs = []
    try:
        data = http_json(f"https://api.github.com/repos/{full_name}/readme")
        content = data.get("content")
        if content:
            return base64.b64decode(content).decode("utf-8", "ignore")[:limit], data.get("html_url", "")
        if data.get("download_url"):
            raw = http_text(data["download_url"], timeout=30)
            return raw[:limit], data.get("html_url", "")
        errs.append("API 无 content/download_url")
    except Exception as e:  # noqa: BLE001
        errs.append(f"API {type(e).__name__}")
    for branch in ("HEAD", "main", "master"):
        for name in ("README.md", "readme.md", "README.MD"):
            url = f"https://raw.githubusercontent.com/{full_name}/{branch}/{name}"
            try:
                raw = http_text(url, timeout=30)
                if raw.strip():
                    return raw[:limit], url
            except Exception:  # noqa: BLE001
                continue
    return f"(README 取不到：{'；'.join(errs)})", ""


def http_text(url: str, timeout: int = 30) -> str:
    for proxy in (False, True):
        try:
            handlers = [urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})] if proxy else []
            opener = urllib.request.build_opener(*handlers)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with opener.open(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1)
    raise last  # type: ignore[misc]


def headings(md: str) -> list[str]:
    return [h.strip("# ").strip() for h in re.findall(r"^#{1,3}\s+.+$", md, re.M)][:12]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("-n", type=int, default=5)
    ap.add_argument("--readme-chars", type=int, default=1800)
    args = ap.parse_args()

    print(f"# 赛道扫描：{args.topic}\n")
    repos = search_repos(args.topic, args.n)
    if not repos:
        print("没搜到仓库。换更通用的关键词（英文通常更全），例如 'llm agent framework'。")
        return 1

    print("| 仓库 | Stars | 语言 | 最近推送 | 一句话 |")
    print("| --- | --- | --- | --- | --- |")
    for r in repos:
        print(f"| [{r['full_name']}]({r['url']}) | {r['stars']:,} | {r['lang']} | {r['pushed']} | {r['desc'][:70]} |")

    top = repos[0]
    md, readme_url = readme_of(top["full_name"], args.readme_chars)
    hs = headings(md)
    print(f"\n## 头部项目拆解：{top['full_name']}（{top['stars']:,}⭐）")
    if md.startswith("(README 取不到"):
        print("\n" + md)
    if hs:
        print("\n**README 结构**：" + " / ".join(hs))
    else:
        print(f"\n**README 没有 markdown 标题**（{len(md)} 字，多为 HTML）——开头如下：")
        print("> " + re.sub(r"\s+", " ", md)[:260])
    NOISE = re.compile(r"(badge|shields|star-history|\.svg|logo|icon|banner)", re.I)
    figs = [u for u in (IMG_RX.findall(md) + IMG_HTML_RX.findall(md)) if not NOISE.search(u)]
    arch = [u for u in figs if ARCH_HINT.search(u)] or figs[:3]
    if arch:
        print("\n**架构图/流程图线索**：")
        for u in arch[:5]:
            if not u.startswith("http"):
                u = f"https://raw.githubusercontent.com/{top['full_name']}/HEAD/" + u.lstrip("./")
            print(f"- {u}")
    if any(ARCH_HINT.search(h) for h in hs):
        print("- README 里有架构相关章节：" +
              "、".join(h for h in hs if ARCH_HINT.search(h)))
    mermaid = len(re.findall(r"```mermaid", md))
    if mermaid:
        print(f"- README 含 {mermaid} 个 mermaid 图（可直接在 Obsidian 渲染）")
    # 判读：活跃度
    print(f"\n**判读**：最近推送 {top['pushed']}，语言 {top['lang']}，"
          f"topics：{', '.join(top['topics'][:8]) or '无'}")
    print(f"README：{readme_url}")
    print(f"\n下一步建议：读它的 architecture 章节 → 画进 `templates/value-chain-map.md` 的中间件层")
    return 0


if __name__ == "__main__":
    sys.exit(main())
