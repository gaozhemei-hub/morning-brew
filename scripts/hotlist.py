#!/usr/bin/env python3
"""五道口AI早咖啡 · 第四块「今日中文热议」

用 newsnow 公开 API 拉多个平台热榜（无需 key、直连可用），压成一段"今天中文互联网在讨论什么"。
对应"社会共识"这条线：热搜反映的是共识的**温度**，不是事实本身——所以只给榜单前几条，不做解读。

用法：
    python3 hotlist.py                 # 默认 6 个源，每源前 5 条
    python3 hotlist.py --per 3
    python3 hotlist.py --ids weibo,zhihu,cls-telegraph
    python3 hotlist.py --all           # 打印所有可用源
"""
from __future__ import annotations

import argparse
import json
import urllib.request

API = "https://newsnow.busiyi.world/api/s?id={sid}"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125 Safari/537.36")

# 按"对用户的目标（AI 产品岗求职 / 投资判断）有用"挑的源，顺序即展示顺序
DEFAULT = [
    ("cls-telegraph", "财联社电报"),
    ("wallstreetcn-quick", "华尔街见闻"),
    ("xueqiu-hotstock", "雪球热股"),
    ("hackernews", "Hacker News"),
    ("v2ex-share", "V2EX"),
    ("sspai", "少数派"),
    ("weibo", "微博热搜"),
    ("zhihu", "知乎热榜"),
]
# 其他已实测可用的 id（--all 时列举）
EXTRA = ["producthunt", "github-trending-today", "juejin", "solidot", "ithome",
         "jin10", "fastbull", "kaopu"]


def fetch_one(sid: str, per: int) -> list[str]:
    try:
        req = urllib.request.Request(API.format(sid=sid), headers={"User-Agent": UA})
        raw = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=20).read()
        j = json.loads(raw.decode("utf-8", "ignore"))
        items = j.get("items") or []
        return [str(i.get("title") or i.get("name") or "").strip()[:70] for i in items[:per] if i.get("title") or i.get("name")]
    except Exception as e:  # noqa: BLE001
        return [f"⚠️ 抓取失败（{type(e).__name__}）"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=5)
    ap.add_argument("--ids", default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        print("默认源：" + "、".join(f"{n}({i})" for i, n in DEFAULT))
        print("备选源：" + "、".join(EXTRA))
        return 0

    wanted = [x.strip() for x in args.ids.split(",") if x.strip()]
    pairs = [(i, n) for i, n in DEFAULT if not wanted or i in wanted]

    print("## 第四块｜今日中文热议（榜单前几条，不做解读）\n")
    for sid, name in pairs:
        rows = fetch_one(sid, args.per)
        print(f"**{name}**")
        for r in rows:
            print(f"- {r}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
