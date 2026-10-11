#!/usr/bin/env python3
"""把当天的抓取 JSON 摊成"给人看/给模型读"的简报，替代内联 python。

为什么需要它：cron 环境会拦截 heredoc 与 `python3 -c`，内联脚本跑不了，
所以一切取数逻辑都必须落在**脚本文件**里。

用法：
    python3 digest_brief.py                      # 今天
    python3 digest_brief.py --date 2026-10-12
    python3 digest_brief.py --layer 商业与战略层  # 只看某一层
    python3 digest_brief.py --max-items 3         # 每源最多列几条
    python3 digest_brief.py --health              # 只看信源健康（给每日回复用）
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"


def load(day: str) -> dict:
    p = OUT / f"{day}.json"
    if not p.exists():
        raise SystemExit(f"✗ 找不到 {p}（先跑 fetch.py）")
    return json.loads(p.read_text(encoding="utf-8"))


def health_lines(d: dict) -> list[str]:
    ok, quiet, bad = [], [], []
    for s in d["sources"]:
        if s["new"] > 0:
            ok.append(f"{s['name']}({s['new']})")
        elif s["total_in_feed"] > 0:
            quiet.append(s["name"])
        else:
            bad.append(s["name"])
    for e in d.get("errors", []):
        bad.append(f"{e['name']}〔{e['error'][:60]}〕")
    return [
        f"✅ 有新增 {len(ok)} 个：" + "、".join(ok),
        f"⚠️ 抓成功但今天无新 {len(quiet)} 个：" + "、".join(quiet),
        f"❌ 抓失败/无内容 {len(bad)} 个：" + ("、".join(bad) if bad else "无"),
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--layer", default="")
    ap.add_argument("--max-items", type=int, default=4)
    ap.add_argument("--health", action="store_true")
    args = ap.parse_args()

    d = load(args.date)

    if args.health:
        print(f"# 信源健康 {args.date}｜源 {len(d['sources'])} 个｜新条目 {sum(s['new'] for s in d['sources'])}")
        for line in health_lines(d):
            print(line)
        return 0

    print(f"# 抓取简报 {args.date}｜窗口 {d['window_days']} 天｜"
          f"源 {len(d['sources'])} 个｜新条目 {sum(s['new'] for s in d['sources'])}")

    layer_now = None
    for s in d["sources"]:
        if args.layer and s["layer"] != args.layer:
            continue
        if s["layer"] != layer_now:
            layer_now = s["layer"]
            print(f"\n【{layer_now}】")
        if not s["items"]:
            print(f"  · {s['name']}（今天无新内容）")
            continue
        print(f"  ▸ {s['name']}｜{s['lens']}｜新 {s['new']}/{s['total_in_feed']}")
        for it in s["items"][: args.max_items]:
            dt = (it.get("date") or "无日期")[:16]
            print(f"      [{dt}] {it['title'][:95]}")
            summ = (it.get("summary") or "").strip().replace("\n", " ")
            if summ:
                print(f"        {summ[:170]}")
            print(f"        {it['url'][:115]}")

    print("\n--- 信源健康 ---")
    for line in health_lines(d):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
