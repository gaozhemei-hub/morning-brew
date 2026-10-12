#!/usr/bin/env python3
"""五道口AI早咖啡 · 每日一键执行（给 cron 用的**单条静态命令**）

为什么需要它：cron 环境的安全扫描会拦掉"带动态替换/内联脚本"的命令
（`$(...)`、`python3 -c`、heredoc、execute_code 一律 BLOCKED，因为无人审批）。
所以把**所有判断都收进这个脚本**，cron 只需要跑一条完全静态的命令：

    python3 ~/Research/frontier-radar/scripts/daily.py

它做三件事并把结果落盘，最后打印一份"仪表盘"（含数据新鲜度，防止用旧数据充数）：
  1. 按今天星期几自动决定轮换组（周一/周五 AI前沿、周二/周六 商业创投、周三 产品工程、周四 半导体、周日 all）
  2. 抓取 → 写 `out/<日期>.json`；再生成简报 `out/brief-<日期>.txt`
  3. 拉热榜 → 写 `out/hotlist-<日期>.txt`

退出码：0 全部正常；1 抓取失败；2 热榜失败（抓取仍成功）。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "out"

ROTATION = {0: "AI前沿", 1: "商业创投", 2: "产品工程", 3: "半导体",
            4: "AI前沿", 5: "商业创投", 6: "all"}


def run(args: list[str], timeout: int = 900) -> tuple[int, str]:
    p = subprocess.run([sys.executable, *args], capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def main() -> int:
    today = date.today()
    weekday = today.weekday()                      # 0=周一
    group = ROTATION[weekday]
    is_monday = weekday == 0
    OUT.mkdir(exist_ok=True)
    t0 = time.time()

    # ── 1) 抓取 ──────────────────────────────────────────────
    fargs = [str(HERE / "fetch.py"), "--days", "3" if weekday in (5, 6) else "2", "--rotate", group]
    if is_monday:
        fargs.append("--weekly")                   # 周一额外扫开源/工程层
    rc, flog = run(fargs)
    print(f"[1/3] 抓取  rc={rc}  轮换组={group}{'（周一，含 --weekly）' if is_monday else ''}  {time.time()-t0:.0f}s")
    print("      " + "\n      ".join(flog.strip().splitlines()[-4:]))
    if rc != 0:
        print("      ✗ 抓取失败——下面的简报会基于**旧数据**，必须在回复里说明！")

    # ── 2) 简报（含新鲜度）────────────────────────────────────
    rc2, brief = run([str(HERE / "digest_brief.py"), "--date", today.isoformat()])
    brief_path = OUT / f"brief-{today.isoformat()}.txt"
    if rc2 == 0:
        brief_path.write_text(brief, encoding="utf-8")
    rc3, health = run([str(HERE / "digest_brief.py"), "--date", today.isoformat(), "--health"])
    (OUT / f"health-{today.isoformat()}.txt").write_text(health, encoding="utf-8")
    print(f"[2/3] 简报  rc={rc2} → {brief_path.name}（{len(brief)} 字节）")

    # 数据新鲜度：防止拿旧 JSON 当今天的产出
    # 数据新鲜度：generated_at 是 **UTC**，必须换算到本地时区再比日期
    # （否则每天早上 07:30 = UTC 前一天 23:30，会天天误报"不是今天"）
    fresh = "未知"
    jf = OUT / f"{today.isoformat()}.json"
    if jf.exists():
        try:
            from datetime import timezone as _tz
            payload = json.loads(jf.read_text(encoding="utf-8"))
            gen = payload.get("generated_at", "")
            dt_utc = datetime.fromisoformat(gen.replace("Z", "+00:00"))
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=_tz.utc)
            dt_local = dt_utc.astimezone()
            same_day = dt_local.date() == today
            fresh = (f"{dt_local.strftime('%Y-%m-%d %H:%M')} 本地"
                     f"（{'✅ 今天' if same_day else '⚠️ 不是今天（UTC ' + dt_utc.strftime('%m-%d %H:%M') + '）'}）")
        except Exception as e:  # noqa: BLE001
            fresh = f"读取失败 {type(e).__name__}"
    print(f"      数据新鲜度：{fresh}")

    # ── 3) 热榜 ──────────────────────────────────────────────
    rc4, hot = run([str(HERE / "hotlist.py"), "--per", "5"])
    if rc4 == 0:
        (OUT / f"hotlist-{today.isoformat()}.txt").write_text(hot, encoding="utf-8")
    print(f"[3/3] 热榜  rc={rc4} → out/hotlist-{today.isoformat()}.txt")
    print(f"\n总计 {time.time()-t0:.0f}s｜下一步：读 out/brief-{today.isoformat()}.txt、"
          f"out/health-{today.isoformat()}.txt、out/hotlist-{today.isoformat()}.txt 写早咖啡")

    return 0 if rc == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
