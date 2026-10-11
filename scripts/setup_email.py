#!/usr/bin/env python3
"""五道口AI早咖啡 · 邮件一键配置（不用手改 .env）

它会：
  1. 告诉你去哪拿 QQ 邮箱授权码
  2. 让你把授权码粘进来（**隐藏输入，看不见也不会打印出来**）
  3. 自动写进 ~/.hermes/.env，并把 PROVIDER 改成 qq
  4. 可选：立刻发一封测试邮件验证

用法：
    python3 setup_email.py              # 引导式配置 + 询问是否发测试邮件
    python3 setup_email.py --check      # 只测试发信（不再输入授权码）
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys
from pathlib import Path

# 优先写仓库自己的 .env（开源用户），没有就写全局
ENV = (Path(__file__).resolve().parent.parent / ".env")
if not ENV.exists():
    ENV = Path.home() / ".hermes" / ".env"
HERE = Path(__file__).resolve().parent
SENDER = HERE / "send_digest.py"
DIGEST_HINT = Path(os.environ.get("MORNING_BREW_VAULT", "~/morning-brew-output")).expanduser()

GUIDE = """
────────────────────────────────────────────────────────────
 QQ 邮箱授权码怎么拿（约 1 分钟）
────────────────────────────────────────────────────────────
 1. 浏览器打开  https://mail.qq.com  登录你的 QQ 邮箱
 2. 点页面顶部「设置」（齿轮图标）→ 左侧选「账户」
 3. 页面向下找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
 4. 找到「IMAP/SMTP服务」那一行，点「开启」
    → 按提示用手机发一条验证短信（绑定手机号）
    → 屏幕上会弹出【16 位授权码】，形如：abcd efgh ijkl mnop
 5. 复制它（空格可留可去），粘到下面。它只用于发信，不是你的登录密码。
    （关了也没关系：同一位置随时能「生成授权码」重新拿一个）
────────────────────────────────────────────────────────────
"""


def read_env_lines() -> list[str]:
    return ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []


def set_kv(lines: list[str], key: str, value: str) -> list[str]:
    out, done = [], False
    for ln in lines:
        if re.match(rf"^\s*{re.escape(key)}\s*=", ln):
            out.append(f"{key}={value}")
            done = True
        else:
            out.append(ln)
    if not done:
        out.append(f"{key}={value}")
    return out


def write_env(lines: list[str]) -> None:
    ENV.parent.mkdir(parents=True, exist_ok=True)
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    try:
        ENV.chmod(0o600)
    except Exception:
        pass


def send_test() -> int:
    md = None
    if DIGEST_HINT.exists():
        cands = sorted(DIGEST_HINT.glob("五道口AI早咖啡-2*.md"))
        md = cands[-1] if cands else None
    if md is None:
        print("（没找到早咖啡文件，用一个临时内容测试）")
        md = Path("/tmp/mb_test.md")
        md.write_text("# 测试邮件\n\n这是一封来自「五道口AI早咖啡」的测试邮件，说明配置成功。\n", encoding="utf-8")
    print(f"\n正在发送测试邮件（用 {md.name}）…")
    r = subprocess.run([sys.executable, str(SENDER), "--md", str(md),
                        "--subject", "五道口AI早咖啡 · 配置测试", "--date", "test"],
                       capture_output=True, text=True)
    print(r.stdout.strip() or r.stderr.strip())
    return r.returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只发测试邮件，不重新输入授权码")
    args = ap.parse_args()

    if args.check:
        raise SystemExit(send_test())

    print(GUIDE)
    try:
        code = getpass.getpass("请粘贴 16 位授权码，然后回车（输入不会显示）：").strip()
    except (KeyboardInterrupt, EOFError):
        print("\n已取消，未做任何修改。")
        return 1

    code = re.sub(r"\s+", "", code)
    if len(code) != 16:
        print(f"\n⚠️ 长度是 {len(code)} 位，QQ 授权码一般是 16 位——请确认复制完整（空格可忽略）。")
        print("   再跑一次这个脚本即可重来。")
        return 2

    lines = read_env_lines()
    if not any(l.startswith("MORNING_BREW_SMTP_USER=") for l in lines):
        print("⚠️ 没在 .env 里找到 MORNING_BREW_* 配置块，我把必要的几行补上。")
        lines += ["", "# ===== 五道口AI早咖啡 · 邮件投递 ====="]
    user = next((l.split("=", 1)[1] for l in lines if l.startswith("MORNING_BREW_SMTP_USER=")), "you@example.com")
    lines = set_kv(lines, "MORNING_BREW_EMAIL_PROVIDER", "qq")
    lines = set_kv(lines, "MORNING_BREW_EMAIL_TO", user)
    lines = set_kv(lines, "MORNING_BREW_EMAIL_FROM", user)
    lines = set_kv(lines, "MORNING_BREW_SMTP_HOST", "smtp.qq.com")
    lines = set_kv(lines, "MORNING_BREW_SMTP_PORT", "465")
    lines = set_kv(lines, "MORNING_BREW_SMTP_USER", user)
    lines = set_kv(lines, "MORNING_BREW_SMTP_PASS", code)
    write_env(lines)

    print(f"\n✓ 已写入配置：provider=qq，收件人={user}，授权码已保存（长度 {len(code)}，未显示）")
    print("✓ 配置文件：~/.hermes/.env\n")

    if sys.stdin.isatty():
        ans = input("现在发一封测试邮件吗？(y/n) ").strip().lower()
        if ans.startswith("y"):
            return send_test()
    print("跳过测试。想测可以随时跑：python3 scripts/setup_email.py --check")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
