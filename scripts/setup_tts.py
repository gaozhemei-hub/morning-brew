#!/usr/bin/env python3
"""五道口AI早咖啡 · 一键配置语音晨报的 StepFun API Key

为什么需要它：Key 是凭据，**不应该出现在聊天记录、命令历史或仓库里**。
这个脚本用隐藏输入（输入时不回显）把 Key 写进 `~/.hermes/.env`，只改这一行，不碰其他配置。

用法：
    python3 scripts/setup_tts.py              # 交互式：粘贴 Key → 写入 → 顺手验证
    python3 scripts/setup_tts.py --no-verify  # 只写入，不调接口
    python3 scripts/setup_tts.py --show       # 只看当前是否已配置（不显示 Key 本身）

写入位置与优先级（与 scripts/send_digest.py / voice_brief.py 一致）：
    仓库内 `.env`  →  `~/.hermes/.env`（后者兜底）
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = "MORNING_BREW_STEPFUN_API_KEY"
GLOBAL_ENV = Path.home() / ".hermes" / ".env"
REPO_ENV = ROOT / ".env"


def target_env() -> Path:
    """仓库里有 .env 就写仓库（开源用户的主路径）；否则写全局。"""
    return REPO_ENV if REPO_ENV.exists() else GLOBAL_ENV


def set_kv(path: Path, key: str, value: str) -> bool:
    """幂等写 key=value：已存在则替换该行，不存在则追加；**其他行原样保留**。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    out, done = [], False
    for line in lines:
        if re.match(rf"^\s*{re.escape(key)}\s*=", line) and not line.strip().startswith("#"):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if not done:
        if out and out[-1].strip():
            out.append("")
        out.append("# ── 语音晨报（StepFun TTS）──")
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return done


def current(path: Path) -> str:
    if not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(rf"^\s*{re.escape(KEY)}\s*=\s*(.*)$", line)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return ""


def mask(v: str) -> str:
    return "（未设置）" if not v else f"已设置 · {len(v)} 字符 · {v[:3]}***{v[-2:]}" if len(v) > 8 else "已设置"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-verify", action="store_true", help="写入后不调用接口验证")
    ap.add_argument("--show", action="store_true", help="只显示当前配置状态")
    ap.add_argument("--doctor", action="store_true", help="只做体检：打印环境与配置状态，不读输入")
    ap.add_argument("--from-clipboard", action="store_true",
                    help="从剪贴板读取 Key（先在浏览器复制好 Key，再跑这条；最省事、不回显）")
    args = ap.parse_args()

    path = target_env()
    print(f"配置文件：{path}")

    if args.doctor:
        print("── 体检 ──")
        print(f"  Python      : {sys.version.split()[0]}（{sys.executable}）")
        print(f"  脚本路径    : {Path(__file__).resolve()}")
        print(f"  仓库根      : {ROOT}")
        print(f"  仓库 .env   : {'存在' if REPO_ENV.exists() else '不存在（会写全局）'}")
        print(f"  全局 .env   : {'存在' if GLOBAL_ENV.exists() else '不存在'}")
        print(f"  将写入      : {target_env()}")
        print(f"  当前 Key    : {mask(current(path))}")
        print(f"  voice_brief : {'存在' if (ROOT / 'scripts' / 'voice_brief.py').exists() else '缺失！'}")
        clip = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout.strip()
        print(f"  剪贴板      : {len(clip)} 字符" + (f" · 形如 {clip[:3]}***" if clip else "（空）"))
        return 0

    if args.show:
        print(f"  {KEY}：{mask(current(path))}")
        print(f"  （仓库 .env 也存在时以它为准：{REPO_ENV.exists()}）")
        return 0

    print(f"  当前：{mask(current(path))}")
    print()
    if args.from_clipboard:
        clip = subprocess.run(["pbpaste"], capture_output=True, text=True).stdout
        key = clip.strip().strip('"').strip("'").split()[0] if clip.strip() else ""
        print("已从剪贴板读取内容。" if key else "✗ 剪贴板是空的——请先在浏览器里复制 Key，再跑这条命令。")
        if not key:
            return 2
    else:
        print("请粘贴 StepFun 开放平台的 API Key，然后回车（输入时不显示，属正常）：")
        try:
            key = getpass.getpass("  API Key: ").strip().strip('"').strip("'")
        except (KeyboardInterrupt, EOFError):
            print("\n已取消，未做任何修改。")
            return 1
    if not key:
        print("✗ 没有输入内容，未做修改。", file=sys.stderr)
        return 2
    if len(key) < 16:
        print(f"✗ 看着不像完整的 Key（只有 {len(key)} 字符）。如果确认没错，加 --force 重试。", file=sys.stderr)
        return 2

    replaced = set_kv(path, KEY, key)
    print(f"✓ 已{'更新' if replaced else '写入'} {KEY}（{len(key)} 字符）→ {path}")
    print("  说明：只改了这一行，其他配置未动；Key 没有经过聊天记录。")

    if args.no_verify:
        return 0
    print("\n顺手验证一下（调 --list-voices，会真的请求接口）：")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "voice_brief.py"), "--list-voices"],
                       capture_output=True, text=True, timeout=90)
    out = (r.stdout or r.stderr).strip()
    print(out[:1200] if out else f"（无输出，退出码 {r.returncode}）")
    if r.returncode == 0:
        print("\n✅ Key 可用。接着就可以跑：")
        print("   python3 scripts/voice_brief.py --md examples/早咖啡-2026-10.md --date 2026-10-12")
        return 0
    print("\n⚠️ 验证没通过。常见原因：① Key 复制不全；② 账号还没做实名认证或没有额度；③ 网络需要代理。", file=sys.stderr)
    return r.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())
