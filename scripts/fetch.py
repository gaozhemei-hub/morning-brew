#!/usr/bin/env python3
"""前沿雷达 · 抓取器（确定性部分）

只做一件事：把 sources.json 里每个源的「新条目」抓成结构化 JSON。
判断（分级/该不该深挖）不做——那是 agent 的活。

用法：
    python3 fetch.py                     # 抓最近 7 天
    python3 fetch.py --days 3 --reset     # 覆盖时间窗 + 忽略 seen 状态
    python3 fetch.py --only a16z,lexfridman
输出：
    stdout 打印摘要表；完整 JSON 写到 out/<date>.json；状态写到 state/seen.json
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "out"
STATE_DIR = ROOT / "state"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
# 代理：默认不启用。需要代理访问海外站点时，设 MORNING_BREW_PROXY（或标准 HTTPS_PROXY）
# 例如：MORNING_BREW_PROXY=http://127.0.0.1:7890
PROXY = os.environ.get("MORNING_BREW_PROXY") or os.environ.get("HTTPS_PROXY") or ""


def fetch(url: str, timeout: int = 40, proxy: bool = False, insecure: bool = False) -> bytes:
    """proxy=True 时走 PROXY；PROXY 为空则直连（不会报错）。"""
    import gzip, zlib, ssl
    handlers = [urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})] if proxy else [urllib.request.ProxyHandler({})]
    if insecure:
        # 少数站点（如晚点 LatePost）证书链不完整，标准校验直接失败。
        # 必须把 HTTPSHandler 一起传进 build_opener —— 建好之后再 add_handler 会被默认 handler 抢先。
        _ctx = ssl.create_default_context()
        _ctx.check_hostname = False
        _ctx.verify_mode = ssl.CERT_NONE
        handlers.append(urllib.request.HTTPSHandler(context=_ctx))
    opener = urllib.request.build_opener(*handlers)
    last: Exception | None = None
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": UA, "Accept": "*/*", "Accept-Encoding": "gzip, deflate"},
            )
            with opener.open(req, timeout=timeout) as r:
                blob = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
            if "gzip" in enc:
                blob = gzip.decompress(blob)
            elif "deflate" in enc:
                blob = zlib.decompress(blob, -zlib.MAX_WBITS)
            return blob
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < 3:
                time.sleep(3 * attempt)
    raise last  # type: ignore[misc]


def parse_hf_daily(blob: bytes) -> list[dict]:
    """Hugging Face Daily Papers API（JSON）。"""
    out = []
    for p in json.loads(blob.decode("utf-8", "ignore")):
        paper = p.get("paper") or {}
        title = (paper.get("title") or "").strip()
        if not title:
            continue
        up = paper.get("upvotes") or 0
        pid = paper.get("id") or ""
        authors = ", ".join((a.get("name") or "") for a in (paper.get("authors") or [])[:3])
        out.append(
            {
                "title": title,
                "url": f"https://huggingface.co/papers/{pid}" if pid else "https://huggingface.co/papers",
                "date": (p.get("publishedAt") or "")[:10],
                "summary": f"👍{up}｜{authors}｜{(paper.get('summary') or '')[:220]}",
            }
        )
    return out


def parse_gh_trending(blob: bytes) -> list[dict]:
    """GitHub Trending 页面：仓库名 + 描述 + 本周星数。
    注意：GitHub 会改 class 名，所以不依赖 h2 的 class，改用「块内第一个形如 /owner/repo 的链接」。"""
    import html as _html

    page = blob.decode("utf-8", "ignore")
    skip = ("/login", "/signup", "/sponsors", "/features", "/topics", "/collections", "/settings")
    out = []
    for block in re.split(r'<article class="Box-row"', page)[1:]:
        repo = next(
            (c for c in re.findall(r'href="(/[A-Za-z0-9_.\-]+/[A-Za-z0-9_.\-]+)"', block)
             if not c.startswith(skip)),
            None,
        )
        if not repo:
            continue
        desc = re.search(r'<p class="[^"]*my-1[^"]*"[^>]*>(.*?)</p>', block, re.S)
        stars = re.search(r"([\d,]+)\s*stars?\s*(?:this week|today)", re.sub(r"<[^>]+>", " ", block))
        lang = re.search(r'itemprop="programmingLanguage">([^<]+)<', block)
        out.append(
            {
                "title": repo.strip("/"),
                "url": "https://github.com" + repo,
                "date": "",
                "summary": "｜".join(
                    x for x in [
                        f"+{stars.group(1)} stars/周" if stars else "",
                        lang.group(1) if lang else "",
                        (_html.unescape(re.sub(r"<[^>]+>", " ", desc.group(1))).strip()[:200] if desc else ""),
                    ] if x
                ),
            }
        )
    return out


def twitter_items(handle: str, limit: int) -> list[dict]:
    """X/Twitter：走 OpenCLI（复用 Chrome 登录态，无需 cookie 环境变量）。"""
    import shutil
    import subprocess

    exe = shutil.which("opencli") or str(Path.home() / ".hermes/tools/node-26.7.0-darwin-arm64/bin/opencli")
    proc = subprocess.run(
        [exe, "twitter", "tweets", handle, "--limit", str(limit), "-f", "json"],
        capture_output=True, text=True, timeout=300,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[:160])
    data = json.loads(proc.stdout)
    rows = data if isinstance(data, list) else data.get("tweets", [])
    out = []
    for t in rows:
        out.append(
            {
                "title": (t.get("text") or "").replace("\n", " ")[:110],
                "url": t.get("url") or f"https://x.com/{handle}",
                "date": t.get("created_at", ""),
                "summary": f"♥{t.get('likes', 0)} 🔁{t.get('retweets', 0)} 👁{t.get('views', 0)}｜"
                           + (t.get("text") or "").replace("\n", " ")[:300],
            }
        )
    return out



def yt_channel_items(channel_url: str, limit: int = 8) -> list[dict]:
    """YouTube 频道最新视频（RSS 有滞后时用；依赖 agent-reach 的 yt-dlp）。"""
    import shutil
    import subprocess

    ytdlp = shutil.which("yt-dlp") or str(Path.home() / ".agent-reach/bin/yt-dlp")
    cmd = [
        ytdlp, "--flat-playlist", "--playlist-end", str(limit),
        "--dump-json", "--no-warnings", channel_url.rstrip("/") + "/videos",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    out = []
    for line in proc.stdout.splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        vid = d.get("id", "")
        out.append(
            {
                "title": d.get("title", ""),
                "url": f"https://www.youtube.com/watch?v={vid}" if vid else d.get("url", ""),
                "date": "",
                "summary": f"[YouTube] 时长 {d.get('duration') or d.get('duration_string') or '?'}",
            }
        )
    return out



def strip_tags(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%d"):
        try:
            d = datetime.strptime(raw.strip(), fmt)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def text_of(el, *names) -> str:
    """按本地名（忽略命名空间）取子元素文本；'link' 优先取 alternate。"""
    want = {n.lower() for n in names}
    for child in el:
        if _local(child.tag) not in want:
            continue
        if _local(child.tag) == "link":
            if child.get("rel") in (None, "alternate"):
                return (child.get("href") or child.text or "").strip()
            continue
        if child.text:
            return child.text.strip()
    # link 兜底：任一 link
    for child in el:
        if _local(child.tag) == "link":
            return (child.get("href") or child.text or "").strip()
    return ""


def parse_feed(blob: bytes) -> list[dict]:
    """兼容 RSS 2.0 / Atom（忽略命名空间）。"""
    root = ET.fromstring(blob)
    items = []
    for it in root.iter():
        if _local(it.tag) not in ("item", "entry"):
            continue
        title = strip_tags(text_of(it, "title"))
        link = text_of(it, "link") or strip_tags(text_of(it, "guid", "id"))
        raw_date = text_of(it, "pubdate", "published", "updated", "date", "created")
        desc = strip_tags(text_of(it, "description", "summary", "content", "encoded"))[:400]
        if not title:
            continue
        items.append({"title": title, "url": link, "date": raw_date, "summary": desc})
    return items


def parse_html_links(blob: bytes, pattern: str, base: str) -> list[dict]:
    """无 RSS 的站：从落地页抽文章链接（标题取锚文本）。"""
    page = blob.decode("utf-8", "ignore")
    rx = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
    seen, out = set(), []
    for href, inner in rx.findall(page):
        if not re.search(pattern, href):
            continue
        title = strip_tags(inner)
        if len(title) < 12 or title.lower().startswith(("read more", "learn more")):
            continue
        url = html.unescape(href)
        # 相对路径必须补全（./x?id=1 这种不以 / 开头，旧版漏掉了）
        url = urllib.parse.urljoin(base, url)
        # 去重键用**完整 URL**：很多站点的文章编号在查询参数里（?id=1848），
        # 旧版砍掉 ?query 后所有文章会塌缩成一条（甲子光年/晚点都踩过这个坑）。
        key = url
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title, "url": url, "date": "", "summary": ""})
    return out


def _dig(obj, path: str):
    """按 'a.b.c' 取嵌套字段；空路径返回 obj 本身。"""
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list) and part.isdigit():
            cur = cur[int(part)] if int(part) < len(cur) else None
        else:
            return None
    return cur


def parse_json_api(blob: bytes, spec: dict) -> list[dict]:
    """通用 JSON API 解析：items_path 定位数组，title/id/date/summary/url 描述字段。"""
    data = json.loads(blob.decode("utf-8", "ignore"))
    items = _dig(data, spec.get("items_path", "")) or []
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        title = str(_dig(it, spec.get("title", "title")) or "").strip()
        if not title:
            continue
        ident = str(_dig(it, spec.get("id", "id")) or "")
        url = spec.get("url", "")
        if url:
            url = url.replace("{id}", ident)
        summary = str(_dig(it, spec.get("summary", "summary")) or "").strip()
        date = str(_dig(it, spec.get("date", "date")) or "").strip()
        out.append({"title": title, "url": url, "date": date[:10], "summary": summary[:300]})
    return out


def parse_sitemap(blob: bytes, pattern: str = "") -> list[dict]:
    """sitemap.xml：抽取 <loc>，按 link_pattern 过滤（a16z 用）。"""
    page = blob.decode("utf-8", "ignore")
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", page)
    out, seen = [], set()
    for u in locs:
        if pattern and not re.search(pattern, u):
            continue
        if u in seen:
            continue
        seen.add(u)
        slug = u.rstrip("/").split("/")[-1].replace("-", " ")
        out.append({"title": slug[:120], "url": u, "date": "", "summary": ""})
    # sitemap 普遍按"旧→新"排列，倒序后新的在前（否则 max_items 只能截到最旧的几条）
    return list(reversed(out))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--only", type=str, default="")
    ap.add_argument("--reset", action="store_true", help="忽略 seen 状态")
    ap.add_argument("--weekly", action="store_true", help="同时也抓 cadence=weekly 的源（GitHub Trending / LangChain 等）")
    ap.add_argument("--rotate", default="", help="轮换组名（AI前沿/商业创投/产品工程/半导体）或 all：只启用对应 rotation_group 的源")
    args = ap.parse_args()

    # 配置查找顺序：sources/sources.json → 根目录 sources.json（兼容旧布局）
    cfg_path = ROOT / "sources" / "sources.json"
    if not cfg_path.exists():
        cfg_path = ROOT / "sources.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    days = args.days if args.days is not None else cfg.get("default_window_days", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state_file = STATE_DIR / "seen.json"
    state: dict = {} if args.reset or not state_file.exists() else json.loads(state_file.read_text())
    seen_all: set[str] = {u for v in state.values() for u in v.get("urls", [])}

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    results, errors = [], []

    for src in cfg["sources"]:
        # 先判 --only（显式指定就一定能跑，忽略 enabled 与轮换）
        if only and src["id"] not in only:
            continue
        rg = src.get("rotation_group")
        # 轮换源：默认 enabled=false，只有当 --rotate 轮到它这一组时才启用。
        # 注意顺序：**必须先判轮换再判 enabled**，否则 enabled=false 会先把它们跳掉（踩过）。
        if not only:
            if rg:
                if not args.rotate or (args.rotate != "all" and args.rotate != rg):
                    continue
            elif not src.get("enabled", True):
                continue
        if src.get("cadence") == "weekly" and not args.weekly and not only:
            continue
        t0 = time.time()
        try:
            use_proxy = bool(src.get("proxy"))
            stype = src["type"]
            insecure = bool(src.get("insecure"))
            blob = None
            if stype in ("rss", "atom"):
                blob = fetch(src["url"], proxy=use_proxy, insecure=insecure)
                raw = parse_feed(blob)
            elif stype == "youtube":
                raw = yt_channel_items(src["url"], int(src.get("max_items", 8)))
            elif stype == "hf_daily":
                raw = parse_hf_daily(fetch(src["url"], proxy=use_proxy, insecure=insecure))
            elif stype == "github_trending":
                raw = parse_gh_trending(fetch(src["url"], proxy=use_proxy, insecure=insecure))
            elif stype == "json_api":
                raw = parse_json_api(fetch(src["url"], proxy=use_proxy, insecure=insecure), src.get("json", {}))
            elif stype == "sitemap":
                raw = parse_sitemap(fetch(src["url"], proxy=use_proxy, insecure=insecure), src.get("link_pattern", ""))
            elif stype == "twitter":
                h = src.get("handle") or src.get("url", "").rstrip("/").split("/")[-1]
                raw = twitter_items(h, int(src.get("max_items", 5)))
            else:
                blob = fetch(src["url"], proxy=use_proxy, insecure=insecure)
                raw = parse_html_links(blob, src.get("link_pattern", "."), src.get("base") or src["url"])
            # 同一源内按标题去重（html 源常有重复锚点/nav）
            dedup, titles = [], set()
            for it in raw:
                k = re.sub(r"\W+", "", it["title"])[:60].lower()
                if not k or k in titles:
                    continue
                titles.add(k)
                dedup.append(it)
            raw = dedup
            fresh = []
            for it in raw:
                d = parse_date(it["date"])
                it["date_parsed"] = d.isoformat() if d else ""
                # 无日期（html/youtube 源）→ 靠 seen 去重；有日期 → 靠时间窗 + seen
                if it["url"] in seen_all:
                    continue
                if d and d < cutoff:
                    continue
                fresh.append(it)
            for it in fresh:
                seen_all.add(it["url"])
            cap = int(src.get("max_items", 25))
            suppressed = max(0, len(fresh) - cap)
            fresh = fresh[:cap]
            results.append(
                {
                    "id": src["id"],
                    "layer": src.get("layer", ""),
                    "name": src["name"],
                    "lens": src["lens"],
                    "ok": True,
                    "total_in_feed": len(raw),
                    "new": len(fresh),
                    "suppressed": suppressed,
                    "seconds": round(time.time() - t0, 1),
                    "items": fresh,
                }
            )
            state.setdefault(src["id"], {})["urls"] = list(
                dict.fromkeys([it["url"] for it in raw][:400] + state.get(src["id"], {}).get("urls", []))
            )[:800]
            state[src["id"]]["last_run"] = datetime.now(timezone.utc).isoformat()
        except Exception as e:  # noqa: BLE001
            errors.append({"id": src["id"], "name": src["name"], "error": f"{type(e).__name__}: {e}"})

    today = datetime.now().strftime("%Y-%m-%d")
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "sources": results,
        "errors": errors,
    }
    (OUT_DIR / f"{today}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"# 前沿雷达抓取 {today} | 窗口 {days} 天 | 新条目 {sum(s['new'] for s in results)}")
    layer_now = None
    for s in results:
        if s["layer"] != layer_now:
            layer_now = s["layer"]
            print(f"\n【{layer_now}】")
        print(f"  {s['lens']:<6} {s['name']:<24} 新 {s['new']:>2} / 源内 {s['total_in_feed']:>4}  ({s['seconds']}s)")
    for e in errors:
        print(f"  ! {e['name']}: {e['error']}")
    print(f"\nJSON → {OUT_DIR / f'{today}.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
