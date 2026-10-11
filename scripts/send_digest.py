#!/usr/bin/env python3
"""五道口AI早咖啡 · 邮件投递

把当天的早咖啡 markdown 发到指定邮箱。发件通道可切换，**开源时别人换成自己的邮箱即可**。

用法：
    python3 send_digest.py --md <早咖啡.md> --date 2026-10-12            # 按 .env 配置发送
    python3 send_digest.py --md <早咖啡.md> --dry-run                    # 只渲染不发信（自检）
    python3 send_digest.py --md <早咖啡.md> --provider none              # 显式跳过发送

配置（环境变量或 ~/.hermes/.env）：
    MORNING_BREW_EMAIL_PROVIDER   qq | gmail | smtp | none
    MORNING_BREW_EMAIL_TO         收件人（别人用的时候换成自己的）
    MORNING_BREW_EMAIL_FROM       发件人
    MORNING_BREW_SMTP_HOST/PORT/USER/PASS
    凭据只从环境读取，**绝不写进仓库、绝不打印**。
"""
from __future__ import annotations

import argparse
import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from pathlib import Path

PRESETS = {
    "qq":    {"host": "smtp.qq.com",     "port": 465},
    "gmail": {"host": "smtp.gmail.com",  "port": 465},
    "smtp":  {},
}


def load_env() -> None:
    """把 ~/.hermes/.env 里的 MORNING_BREW_* 读进环境（已存在的环境变量优先）。"""
    # 优先级：仓库根目录 .env（项目自带配置） → ~/.hermes/.env（全局）
    root_env = Path(__file__).resolve().parent.parent / ".env"
    for path in (root_env, Path.home() / ".hermes" / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            # **配置文件对本项目的 key 有最终解释权**：一律覆盖，
            # 否则外部环境里残留的空值/旧值（踩过：空 PASS 盖住真授权码 → 静默发不出去）会赢。
            if k.startswith("MORNING_BREW_"):
                os.environ[k] = v


def md_to_html(md: str, title: str) -> str:
    """极简 markdown → HTML（够用于邮件；不引第三方依赖）。"""
    import html as _html

    out: list[str] = []
    in_ul = False
    in_quote = False

    def close_blocks():
        nonlocal in_ul, in_quote
        if in_ul:
            out.append("</ul>")
            in_ul = False
        if in_quote:
            out.append("</blockquote>")
            in_quote = False

    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            close_blocks()
            continue
        # 引用块：> 开头（QQ 邮箱里必须显式渲染，否则会原样显示 ">"）
        q = re.match(r"^\s*>\s?(.*)$", line)
        if q:
            if in_ul:
                out.append("</ul>"); in_ul = False
            if not in_quote:
                out.append("<blockquote style=\"margin:8px 0;padding:6px 12px;border-left:3px solid #d0d0d0;color:#666\">")
                in_quote = True
            if q.group(1).strip():
                out.append(f"<p style='margin:4px 0'>{inline(q.group(1))}</p>")
            continue
        # 分隔线
        if re.match(r"^\s*([-*_])\1{2,}\s*$", line):
            close_blocks()
            out.append("<hr style='border:none;border-top:1px solid #e5e5e5;margin:16px 0'>")
            continue
        if line.startswith("| "):          # 表格行：邮件里降级成等宽文本，保证可读
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            out.append("<div style='font-family:monospace;font-size:13px'>" + " ｜ ".join(_html.escape(c) for c in cells) + "</div>")
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            if in_quote:
                out.append("</blockquote>"); in_quote = False
            lvl = len(m.group(1))
            size = {1: 22, 2: 18, 3: 16, 4: 15}[lvl]
            out.append(f"<h{lvl} style='font-size:{size}px;margin:18px 0 8px'>{_html.escape(m.group(2))}</h{lvl}>")
            continue
        if re.match(r"^\s*[-*]\s+", line):
            if in_quote:
                out.append("</blockquote>"); in_quote = False
            indent = len(line) - len(line.lstrip())
            if not in_ul:
                out.append("<ul style='margin:6px 0 6px 18px;padding:0'>")
                in_ul = True
            body = re.sub(r"^\s*[-*]\s+", "", line)
            pad = " style='margin:4px 0 4px 18px'" if indent >= 2 else " style='margin:4px 0'"
            out.append(f"<li{pad}>{inline(body)}</li>")
            continue
        if re.match(r"^\s*\d+\.\s+", line):
            body = re.sub(r"^\s*\d+\.\s+", "", line)
            out.append(f"<div style='margin:6px 0'>{inline(body)}</div>")
            continue
        out.append(f"<p style='margin:8px 0'>{inline(line)}</p>")
    close_blocks()
    body = "\n".join(out)
    return (
        "<html><body style=\"font-family:-apple-system,'PingFang SC',sans-serif;"
        "max-width:760px;margin:0 auto;padding:16px;line-height:1.65;color:#222\">"
        f"<h1 style='font-size:24px'>{_html.escape(title)}</h1>{body}</body></html>"
    )


def inline(text: str) -> str:
    """粗体、行内代码、裸链接、Obsidian 双链（邮件里降级成纯文本名）。"""
    import html as _html

    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)   # [[文件#锚点|显示名]] → 显示名
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = _html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"<(https?://[^>]+)>", r'<a href="\1">\1</a>', text)
    text = re.sub(r"(?<![\"'=])(https?://[^\s<)]+)", r'<a href="\1">\1</a>', text)
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True, help="早咖啡 markdown 文件")
    ap.add_argument("--date", default="", help="日期，用于主题")
    ap.add_argument("--subject", default="", help="自定义邮件主题")
    ap.add_argument("--to", default="", help="覆盖收件人")
    ap.add_argument("--provider", default="", help="覆盖 provider：qq/gmail/smtp/none")
    ap.add_argument("--dry-run", action="store_true", help="只渲染不发信")
    args = ap.parse_args()

    load_env()
    md_path = Path(args.md).expanduser()
    if not md_path.exists():
        print(f"✗ 找不到文件：{md_path}", file=sys.stderr)
        return 2
    md = md_path.read_text(encoding="utf-8")

    provider = (args.provider or os.environ.get("MORNING_BREW_EMAIL_PROVIDER", "none")).lower()
    to = args.to or os.environ.get("MORNING_BREW_EMAIL_TO", "")
    frm = os.environ.get("MORNING_BREW_EMAIL_FROM", "") or os.environ.get("MORNING_BREW_SMTP_USER", "")
    subject = args.subject or f"五道口AI早咖啡 {args.date or '(未标日期)'}"
    html = md_to_html(md, subject)

    if args.dry_run or provider in ("none", ""):
        out = Path("/tmp/morning_brew_preview.html")
        out.write_text(html, encoding="utf-8")
        print(f"[dry-run] provider={provider or 'none'}｜收件人={to or '(未设，将只输出本地文件)'}｜未配凭据也能跑通")
        print(f"[dry-run] HTML 预览已写入 {out}（{len(html)} 字节）")
        return 0

    preset = PRESETS.get(provider, {})
    host = os.environ.get("MORNING_BREW_SMTP_HOST") or preset.get("host", "")
    port = int(os.environ.get("MORNING_BREW_SMTP_PORT") or preset.get("port", 465))
    user = os.environ.get("MORNING_BREW_SMTP_USER", "")
    pwd = os.environ.get("MORNING_BREW_SMTP_PASS", "")

    missing = [k for k, v in {"host": host, "to": to, "user": user, "pass": pwd}.items() if not v]
    if missing:
        print(f"✗ 配置不完整，缺少：{', '.join(missing)}（授权码请填在 ~/.hermes/.env）", file=sys.stderr)
        return 3

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = frm or user
    msg["To"] = to
    msg.set_content("本邮件为 HTML 格式，请用支持 HTML 的客户端查看。")
    msg.add_alternative(html, subtype="html")

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=ctx, timeout=45) as s:
        s.login(user, pwd)
        s.send_message(msg)
    print(f"✓ 已发送：{subject} → {to}（provider={provider}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
