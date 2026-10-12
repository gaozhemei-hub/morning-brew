#!/usr/bin/env python3
"""设置「早咖啡」的每日运行时间（**给下载项目的人自定义**）

用法：
    python3 scripts/install_schedule.py                      # 打印 07:30 的安装方式（默认）
    python3 scripts/install_schedule.py --at 08:40           # 改成 08:40 并打印
    python3 scripts/install_schedule.py --at 08:40 --install # 直接写入系统 crontab（幂等）
    python3 scripts/install_schedule.py --show               # 看当前已安装的时间

两种部署方式都支持，随你环境：
  A) 系统 crontab（任何 macOS/Linux 都能用）—— `--install` 会写入一段带标记的任务
  B) Hermes Agent 的定时任务（如果你的 agent 支持 cronjob）—— 打印对应的设置
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MARK_BEGIN = "# >>> morning-brew（五道口AI早咖啡）>>>"
MARK_END = "# <<< morning-brew <<<"
ROOT = Path(__file__).resolve().parent.parent
DAILY = ROOT / "scripts" / "daily.py"


def crontab_line(at: str) -> str:
    hh, mm = at.split(":")
    return f"{int(mm)} {int(hh)} * * * /usr/bin/env python3 {DAILY} >> {ROOT}/out/cron.log 2>&1"


def read_crontab() -> str:
    p = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else ""


def show() -> int:
    cur = read_crontab()
    m = re.search(re.escape(MARK_BEGIN) + r"(.*?)" + re.escape(MARK_END), cur, re.S)
    print("当前 crontab 里的早咖啡任务：")
    print("  " + (m.group(1).strip() if m else "（未安装）"))
    return 0


def install(at: str) -> int:
    hh, mm = at.split(":")
    if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
        print(f"✗ 时间不合法：{at}", file=sys.stderr)
        return 2
    block = f"{MARK_BEGIN}\n{crontab_line(at)}\n{MARK_END}"
    cur = read_crontab()
    if MARK_BEGIN in cur:
        cur = re.sub(re.escape(MARK_BEGIN) + r".*?" + re.escape(MARK_END), block, cur, flags=re.S)
    else:
        cur = (cur.rstrip("\n") + "\n\n" + block + "\n").lstrip("\n")
    p = subprocess.run(["crontab", "-"], input=cur, text=True, capture_output=True)
    if p.returncode != 0:
        print("✗ 写入 crontab 失败：", p.stderr.strip(), file=sys.stderr)
        return 3
    print(f"✓ 已安装：每天 {at} 运行 daily.py（crontab 标记块已更新）")
    print("  提示：macOS 合盖会睡眠 → 任务不会跑。插电+外接显示器，或参考 README「定时」一节。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--at", default="07:30", help="每天运行时间，HH:MM（24 小时制）")
    ap.add_argument("--install", action="store_true", help="直接写入系统 crontab（幂等）")
    ap.add_argument("--show", action="store_true", help="显示当前已安装的时间")
    a = ap.parse_args()

    if a.show:
        return show()
    if a.install:
        return install(a.at)

    hh, mm = a.at.split(":")
    print(f"要把「五道口AI早咖啡」设在每天 {a.at} 运行，二选一：\n")
    print("【A】系统 crontab（推荐，最通用）")
    print("    跑这一条即可自动装好：")
    print(f"      python3 {ROOT}/scripts/install_schedule.py --at {a.at} --install")
    print("    或者手动 `crontab -e`，加入这一行：")
    print(f"      {crontab_line(a.at)}\n")
    print("【B】如果你的 agent 支持定时任务（如 Hermes）")
    print("    新建一个每日任务，让它跑这一条命令即可：")
    print(f"      python3 {DAILY}")
    print(f"    时间设为 {a.at}。任务提示词可参考 skills/morning-brew/SKILL.md。\n")
    print("⚠️ 注意：macOS 合盖会睡眠，任务不会按时跑。")
    print("   → 插电 + 外接显示器（clamshell），或 `sudo pmset -a disablesleep 1`（合盖不睡，注意散热）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
