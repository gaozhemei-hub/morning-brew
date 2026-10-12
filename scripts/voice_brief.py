#!/usr/bin/env python3
"""五道口AI早咖啡 · 语音晨报（通勤收听版）

为什么不是"把晨报直接念出来"：晨报是写给眼睛的。双链 [[...]]、链接、↗、分点符号会被念出来或造成怪停顿；
耳朵不能回看，长段分点听三条就忘。所以这里做的是**把阅读稿改写成收听稿**，而不是简单接一个 TTS。

流水线（每一步都可单独验证）：
  1. 取当天章节 → 解析条目（层级 / 标题 / [必须知道]·[值得知道] / 核心观点 / 为什么现在）
  2. 按时长预算取舍：[必须知道] 完整播、[值得知道] 只播一句、热榜与三件套不播
  3. 大模型改写成口语稿（结论先行、口头路标、术语一句话解释）
     → **数字一致性校验**：改写稿里出现原文没有的数字 → 该段回退为规则稿（宁缺勿错，防止"念错数字"）
  4. 读法规范化（规则先行、词典兜底）：18%→34%、245MW、2026-10-11、GPT-5、a16z …
  5. 按句切块（接口单次上限 1000 字）→ 调阶跃 TTS → 拼接 mp3 → 生成章节时间戳
  6. 落盘：out/voice-<日期>.mp3 / .md（章节目录 + 播报稿 + 质检记录）/ .json（状态，供邮件读取）

**禁止静默失败**：任何一步失败都写进 out/voice-<日期>.json 的 status/reason，邮件会如实说明，文字版照发。

用法：
    python3 scripts/voice_brief.py --md <早咖啡.md> --date 2026-10-12            # 完整生成
    python3 scripts/voice_brief.py --md <早咖啡.md> --date 2026-10-12 --dry-run  # 不调任何接口，只出规则稿，自检用
    python3 scripts/voice_brief.py --md <早咖啡.md> --no-llm                     # 不改写，规则稿直接合成
    python3 scripts/voice_brief.py --list-voices                                 # 列出可用音色

配置（.env，见 .env.example）：
    MORNING_BREW_STEPFUN_API_KEY   阶跃开放平台 API Key（也认 STEPFUN_API_KEY）
    MORNING_BREW_TTS_MODEL         默认 stepaudio-2.5-tts
    MORNING_BREW_TTS_VOICE         默认 cixingnansheng（以 --list-voices 实际返回为准）
    MORNING_BREW_TTS_INSTRUCTION   播报风格（仅 stepaudio 系列支持，≤200 字）
    MORNING_BREW_LLM_MODEL         改写用的对话模型，默认 step-3.5-flash
    MORNING_BREW_VOICE_MINUTES     目标时长（分钟），默认 10

退出码：0 成功；1 部分成功（有段落合成失败，已在状态里列出）；2 失败（无音频产出）；3 输入问题。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "out"
DICT_PATH = ROOT / "sources" / "pronunciation.json"

API_BASE = "https://api.stepfun.com/v1"
CHARS_PER_MIN = 340          # 实测：2173 字播了 6 分 24 秒（≈340 字/分钟，含 instruction 语气、语速 1.0）
                             # 原写 270（行业经验值）会导致 10 分钟目标只产出约 6.4 分钟音频
TTS_MAX_CHARS = 900          # 接口单次上限 1000 字，超出会被**静默截断**，留余量
DEFAULT_INSTRUCTION = "晨间新闻播报，语气清晰沉稳、节奏明快，关键数字和结论稍作强调"


# ───────────────────────── 配置 ─────────────────────────
def load_env() -> None:
    """与 send_digest.py 同一套规则：仓库 .env → ~/.hermes/.env，本项目 key 以配置文件为准。"""
    root_env = ROOT / ".env"
    for path in (root_env, Path.home() / ".hermes" / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.split(" #")[0].strip().strip('"').strip("'")
            if k.startswith("MORNING_BREW_") or k == "STEPFUN_API_KEY":
                os.environ[k] = v


def cfg(key: str, default: str = "") -> str:
    return os.environ.get(f"MORNING_BREW_{key}", "") or default


def api_key() -> str:
    return cfg("STEPFUN_API_KEY") or os.environ.get("STEPFUN_API_KEY", "")


# ───────────────────────── 1. 解析 ─────────────────────────
@dataclass
class Item:
    layer: str
    title: str
    tag: str                       # 必须知道 / 值得知道 / ""
    points: list[str] = field(default_factory=list)
    why: str = ""


def extract_day(md: str, day: str) -> str:
    """月度文件里取 `## YYYY-MM-DD` 章节；单日文件（没有日期标题）直接返回全文。"""
    heads = list(re.finditer(r"^##\s+(\d{4}-\d{2}-\d{2})", md, flags=re.M))
    if not heads:
        return md
    for i, h in enumerate(heads):
        if h.group(1) == day:
            end = heads[i + 1].start() if i + 1 < len(heads) else len(md)
            return md[h.start():end]
    return ""


def clean(text: str) -> str:
    """去掉只对眼睛有意义的东西：双链、链接、强调符号、↗、★、行内代码。"""
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]#]+#)?([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", text)
    text = re.sub(r"<https?://[^>]+>|https?://\S+", "", text)
    text = re.sub(r"`\[(必须知道|值得知道)\]`", "", text)
    text = text.replace("↗", "").replace("★", "").replace("`", "")
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ：:")


def parse_items(day_md: str) -> tuple[str, list[Item]]:
    overview, items, layer, cur, field_ = "", [], "", None, ""
    for raw in day_md.splitlines():
        line = raw.rstrip()
        if re.match(r"^#\s+★", line) or re.match(r"^#\s+四", line):       # 三件套 / 热榜：不播
            break
        m = re.match(r"^#\s+[一二三四五]、\s*(\S+?)（", line)
        if m:
            layer = m.group(1)
            continue
        if line.startswith("**本期速览**"):
            overview = clean(line.split("：", 1)[-1])
            continue
        m = re.match(r"^###\s+(\d+)\.\s+(.*)$", line)
        if m:
            tag = re.search(r"\[(必须知道|值得知道)\]", m.group(2))
            cur = Item(layer=layer, title=clean(m.group(2)), tag=tag.group(1) if tag else "")
            items.append(cur)
            field_ = ""
            continue
        if cur is None:
            continue
        # ★ 必须顶格：字段行在缩进 0，分点在缩进 2。
        #   若这里写成 ^\s*- ，则 `  - **公司名**：…` 这种分点会被当成"字段行"吞掉，
        #   并把 field_ 重置为空，导致紧随其后的普通分点也一起丢（实测 4 条条目正文全空）。
        m = re.match(r"^-\s+\*\*(.+?)\*\*[：:]?\s*(.*)$", line)
        if m:
            name, rest = m.group(1), m.group(2)
            field_ = "points" if "核心观点" in name else "why" if "为什么现在" in name else ""
            if field_ == "why" and rest:
                cur.why = clean(rest)
            elif field_ == "points" and rest:
                cur.points.append(clean(rest))
            continue
        m = re.match(r"^\s{2,}-\s+(.*)$", line)
        if m and field_ == "points":
            cur.points.append(clean(m.group(1)))
    return overview, items


# ───────────────────────── 2. 取舍 ─────────────────────────
def select(items: list[Item], budget_chars: int) -> tuple[list[Item], list[Item], list[Item]]:
    """[必须知道] 按原顺序完整播，直到用完 ~80% 预算；[值得知道] 只播标题；放不下的列进"本期未播"。"""
    must = [i for i in items if i.tag == "必须知道"]
    worth = [i for i in items if i.tag != "必须知道"]
    full, brief, dropped, used = [], [], [], 0
    for it in must:
        cost = len(it.title) + sum(len(p) for p in it.points) + len(it.why)
        if used + cost <= budget_chars * 0.8 or not full:
            full.append(it); used += cost
        else:
            dropped.append(it)
    for it in worth:
        if used + len(it.title) + 10 <= budget_chars:
            brief.append(it); used += len(it.title) + 10
        else:
            dropped.append(it)
    return full, brief, dropped


# ───────────────────────── 3. 改写 ─────────────────────────
@dataclass
class Segment:
    title: str
    text: str
    source: str = "rule"           # rule / llm / llm→rule（数字校验未过回退）
    note: str = ""


CN_NUM = "一二三四五六七八九十"
_CN = {c: i for i, c in enumerate("零一二三四五六七八九")}


def cn_num(n: int) -> str:
    """1→一、12→十二、20→二十（支持到 99），用于把清单条数写进提示词与校验。"""
    d = "零一二三四五六七八九"
    if n < 10:
        return d[n]
    if n < 20:
        return "十" + (d[n - 10] if n > 10 else "")
    return d[n // 10] + "十" + (d[n % 10] if n % 10 else "")


def cn_to_int(s: str) -> int | None:
    """「十三」→13、「二十」→20、「七」→7。"""
    if not s:
        return None
    if "十" in s:
        a, _, b = s.partition("十")
        return (_CN.get(a, 1) if a else 1) * 10 + (_CN.get(b, 0) if b else 0)
    return _CN.get(s)


def check_counts(segs_raw: list[dict], n_brief: int) -> str:
    """校验改写稿的条数：快讯必须正好 n_brief 条。
    实测踩过：速览里提到被筛掉的条目，改写稿会顺手补成一条（12 条变成念到"第十三条"）。"""
    quick = " ".join(str(s.get("text", "")) for s in segs_raw if "快讯" in str(s.get("title", "")))
    if not quick:
        return "改写稿里找不到「快讯」段"
    idx = [i for i in (cn_to_int(x) for x in re.findall(r"第([一二三四五六七八九十]+)条", quick)) if i]
    if not idx:
        return "快讯段没有条目编号，无法核对条数"
    if max(idx) != n_brief:
        return f"快讯条数不符：清单 {n_brief} 条，改写稿念到第 {max(idx)} 条（疑似从速览补了条目）"
    return ""


def short_overview(text: str, limit: int = 150) -> str:
    """速览只取主句，并在句读处截断，避免念到半句。"""
    text = re.split(r"[（(]同日|[（(]补抓", text)[0].strip()
    if len(text) <= limit:
        return text
    cut = max(text.rfind(ch, 0, limit) for ch in "；。，")
    return text[:cut] + "。" if cut > 0 else text[:limit]


def rule_script(day: str, overview: str, full: list[Item], brief: list[Item]) -> list[Segment]:
    """不依赖大模型的保底稿：结构完整、读起来像播报，但不够口语。也是改写失败时的回退。"""
    d = date.fromisoformat(day)
    wk = "一二三四五六日"[d.weekday()]
    segs = [Segment("开场", f"早上好，这里是五道口AI早咖啡，今天是{d.month}月{d.day}日，星期{wk}。"
                             f"今天精选{len(full)}条必须知道、{len(brief)}条值得知道。"
                             + (f"先说一句话速览：{short_overview(overview)}" if overview else ""))]
    last_layer = ""
    for n, it in enumerate(full, 1):
        lead = f"进入{it.layer}。" if it.layer and it.layer != last_layer else ""
        last_layer = it.layer
        body = "；".join(p.rstrip("。") for p in it.points[:3])
        why = f"为什么值得关注：{it.why}" if it.why else ""
        mid = f"{body}。" if body else ""
        segs.append(Segment(f"{n}. {it.title}", f"{lead}第{CN_NUM[n-1] if n <= 10 else n}条，{it.title}。{mid}{why}"))
    if brief:
        lines = "；".join(f"{it.title}" for it in brief)
        segs.append(Segment("快讯", f"再快速过几条值得知道的：{lines}。"))
    segs.append(Segment("结尾", "以上就是今天的早咖啡。完整内容、来源链接和术语解释，都在今天的文字版里。祝你今天顺利。"))
    return segs


REWRITE_PROMPT = """你是一档 AI 行业晨间音频节目的撰稿人。下面是今天文字版晨报的条目（JSON），请改写成**给耳朵听的播报稿**。

要求：
1. 听众在通勤，不能回看。每条**先说结论**，再用 1–2 句说原因，最后一句说"这对你意味着什么"。
2. 用口头路标串起来："第一条""进入技术层""最后快速过几条"。条与条之间不要重复寒暄。
3. 术语第一次出现时，用半句大白话解释（例如"KV Cache，也就是模型推理时的缓存"）。
4. **只能使用原文出现过的数字和事实**，不得补充任何新数字、新人名、新公司；拿不准就删掉，不要猜。
5. 不要输出任何符号化格式：不要括号注释、不要列表符号、不要链接、不要 emoji。
6. 总长度控制在 {budget} 字左右。完整播报的条目每条 150–250 字；快讯部分每条一句话。
7. **条数必须严格等于给定清单**：完整播报正好 {n_full} 条，快讯正好 {n_brief} 条；
   快讯的编号必须从"第一条"连续到"第{n_brief_cn}条"，不得多一条、不得少一条。
8. **「今日速览」只用于开场的一句话概述**，不得从中补充任何条目——它可能包含本期**不播**的内容。
9. **开场必须报出节目名「五道口AI早咖啡」**，然后报日期与条数。
10. **不要解释单位或数字**（例如不要写"245兆瓦也就是…"），直接念出来即可；术语只在确有歧义时用半句解释。

只输出 JSON，格式：
{{"segments": [{{"title": "开场", "text": "..."}}, {{"title": "1. 条目短标题", "text": "..."}}, ..., {{"title": "快讯", "text": "..."}}, {{"title": "结尾", "text": "..."}}]}}
段落顺序与输入一致，开场要报日期（{date_cn}）和今天的条数。

今日速览：{overview}

完整播报条目：
{full_json}

只播一句的快讯条目：
{brief_json}
"""


def http_json(path: str, payload: dict | None, timeout: int = 120, raw: bool = False):
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None,
        headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
        ctype = r.headers.get("Content-Type", "")
    if raw:
        return body, ctype
    return json.loads(body.decode("utf-8"))


def numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:\.\d+)?", text))


def llm_script(day: str, overview: str, full: list[Item], brief: list[Item],
               budget: int, fallback: list[Segment]) -> tuple[list[Segment], str, dict[str, int]]:
    d = date.fromisoformat(day)
    # ★ 关键：先把条目文本做一遍「读法规范化」再交给模型。
    #   否则模型看到 "245MW" 会按"术语要解释"的要求写出"245兆瓦，也就是功率单位兆瓦的"这种冗余
    #   ——它是在给一个**已经转成中文的单位**做注释。让它看不到 MW，问题就不存在。
    _w, _h = load_dict(), {}          # _h 记录「送进模型之前」的规范化命中，供质检记录使用
    nz = lambda t: normalize(t, _w, _h)          # noqa: E731
    full_view = [{"层": i.layer, "标题": nz(i.title), "核心观点": [nz(p) for p in i.points],
                  "为什么现在": nz(i.why)} for i in full]
    brief_view = [{"层": i.layer, "标题": nz(i.title)} for i in brief]
    prompt = REWRITE_PROMPT.format(
        budget=budget, n_full=len(full), n_brief=len(brief), n_brief_cn=cn_num(len(brief)),
        date_cn=f"{d.month}月{d.day}日 星期{'一二三四五六日'[d.weekday()]}",
        overview=normalize(overview, _w, _h) or "（无）",
        full_json=json.dumps(full_view, ensure_ascii=False, indent=1),
        brief_json=json.dumps(brief_view, ensure_ascii=False, indent=1),
    )
    try:
        resp = http_json("/chat/completions", {
            "model": cfg("LLM_MODEL", "step-3.5-flash"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        }, timeout=180)
        content = resp["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", content, flags=re.S)
        segs_raw = json.loads(m.group(0))["segments"] if m else []
    except Exception as e:  # noqa: BLE001
        return fallback, f"改写失败（{type(e).__name__}: {str(e)[:120]}），整篇使用规则稿", _h
    if not segs_raw:
        return fallback, "改写返回为空或非 JSON，整篇使用规则稿", _h

    # 条数校验：先把"从速览补条目"这类幻觉拦下来
    cnt_issue = check_counts(segs_raw, len(brief))
    if cnt_issue:
        return fallback, f"改写稿未通过条数校验（{cnt_issue}），整篇使用规则稿", _h

    # 数字一致性校验：改写稿出现原文没有的数字 → 该段回退规则稿
    allowed = numbers_in(json.dumps(full_view, ensure_ascii=False)
                         + json.dumps(brief_view, ensure_ascii=False) + overview + day)
    allowed |= {str(n) for n in range(0, 32)}                     # 序号、日期等小数字放行
    by_title = {s.title.split(". ", 1)[-1][:6]: s for s in fallback}
    out, flagged = [], []
    for s in segs_raw:
        title, text = str(s.get("title", "")).strip(), clean(str(s.get("text", "")))
        if not text:
            continue
        extra = numbers_in(text) - allowed
        if extra:
            fb = by_title.get(title.split(". ", 1)[-1][:6])
            flagged.append(f"{title}：新增数字 {sorted(extra)}")
            if fb:
                out.append(Segment(fb.title, fb.text, "llm→rule", f"改写稿出现原文没有的数字 {sorted(extra)}，已回退"))
            # 找不到对应规则段时宁可不播这一段，也不播可能错误的数字
            continue
        out.append(Segment(title, text, "llm"))
    note = "改写完成" + (f"；{len(flagged)} 段未通过数字校验已回退：" + "；".join(flagged) if flagged else "，数字校验全部通过")
    return out, note, _h


# ───────────────────────── 4. 读法规范化 ─────────────────────────
def load_dict() -> dict[str, str]:
    try:
        d = json.loads(DICT_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in d.items() if not k.startswith("_")}
    except Exception:  # noqa: BLE001
        return {}


UNITS = {"GW": "吉瓦", "MW": "兆瓦", "kW": "千瓦", "KW": "千瓦", "TB": "TB", "PB": "PB", "pp": "个百分点"}


def normalize(text: str, words: dict[str, str], hits: dict[str, int]) -> str:
    def sub(name: str, pattern: str, repl, s: str, flags: int = 0) -> str:
        new, n = re.subn(pattern, repl, s, flags=flags)
        if n:
            hits[name] = hits.get(name, 0) + n
        return new

    # 词典优先（长词先替换，避免 "KV Cache" 被 "KV" 抢先）
    for k in sorted(words, key=len, reverse=True):
        pat = (r"(?<![A-Za-z0-9])" + re.escape(k) + r"(?![A-Za-z0-9])") if re.search(r"[A-Za-z]", k) else re.escape(k)
        text = sub(f"词典:{k}", pat, words[k], text)
    text = sub("日期", r"(\d{4})-(\d{1,2})-(\d{1,2})", lambda m: f"{m[1]}年{int(m[2])}月{int(m[3])}日", text)
    text = sub("美元缩写", r"\$(\d+(?:\.\d+)?)\s*([BMK])\b",
               lambda m: {"B": f"{float(m[1])*10:g}亿美元", "M": f"{float(m[1])*100:g}万美元",
                          "K": f"{float(m[1])*1000:g}美元"}[m[2]], text)
    text = sub("美元符号", r"\$(\d+(?:\.\d+)?)", r"\1美元", text)
    text = sub("数字箭头", r"(\d%?)\s*[→⇒➜]\s*(?=[A-Za-z]?\d)", r"\1到", text)
    text = sub("百分比", r"(\d+(?:\.\d+)?)\s*%", r"百分之\1", text)
    text = sub("单位", r"(\d)\s*(GW|MW|kW|KW|pp)\b", lambda m: m[1] + UNITS[m[2]], text)
    text = sub("倍数", r"(\d+(?:\.\d+)?)\s*[x×]\b", r"\1倍", text)
    text = sub("箭头", r"\s*[→⇒➜]\s*", "，再到", text)
    text = sub("加号", r"(\d)\+", r"\1多", text)
    text = sub("连接加号", r"\s+\+\s+", "和", text)
    text = sub("破折号", r"\s*(——|—)\s*", "，", text)
    text = sub("括号", r"[（(]([^（）()]{1,40})[）)]", r"，\1，", text)
    text = sub("数字区间", r"(\d)\s*[~～–—-]\s*(\d)", r"\1到\2", text)
    text = sub("型号连字符", r"(?<=[A-Za-z])-(?=\d)", " ", text)
    text = sub("分隔符", r"\s*[｜|/]\s*(?=[一-龥])", "、", text)
    text = sub("残留符号", r"[#*_>【】\[\]{}<>]", "", text)
    text = re.sub(r"，\s*([，。；：！？])", r"\1", text)
    text = re.sub(r"([。；：！？])\s*，", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    # 替换残留的空格（"245MW 站点"→"245兆瓦 站点"、"80+ 服务"→"80多 服务"）：
    # 中文与中文之间的空格在播报稿里永远是噪音，直接去掉。
    for _ in range(3):
        text = re.sub(r"([\u4e00-\u9fff])\s+([\u4e00-\u9fff])", r"\1\2", text)
    text = re.sub(r"([。；：！？，])\1+", r"\1", text)   # 「。。」这类叠标点
    return text


# ───────────────────────── 5. 合成 ─────────────────────────
def chunks(text: str, limit: int = TTS_MAX_CHARS) -> list[str]:
    parts, buf = [], ""
    for sent in re.split(r"(?<=[。！？；\n])", text):
        if len(sent) > limit:                                    # 超长单句再按逗号切
            for sub in re.split(r"(?<=[，、,])", sent):
                if len(buf) + len(sub) > limit and buf:
                    parts.append(buf); buf = ""
                buf += sub
            continue
        if len(buf) + len(sent) > limit and buf:
            parts.append(buf); buf = ""
        buf += sent
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def tts(text: str) -> bytes:
    model = cfg("TTS_MODEL", "stepaudio-2.5-tts")
    payload = {"model": model, "input": text, "voice": cfg("TTS_VOICE", "cixingnansheng"),
               "response_format": "mp3", "speed": 1.0}
    if "stepaudio" in model:
        payload["instruction"] = cfg("TTS_INSTRUCTION", DEFAULT_INSTRUCTION)[:200]
    last = None
    for attempt in range(2):                                     # 网络抖动/5xx 重试一次，4xx 不重试
        try:
            body, ctype = http_json("/audio/speech", payload, timeout=120, raw=True)
            if "json" in ctype or body[:1] == b"{":
                raise RuntimeError(f"接口返回非音频：{body[:200].decode('utf-8', 'ignore')}")
            return body
        except urllib.error.HTTPError as e:
            detail = e.read()[:200].decode("utf-8", "ignore")
            last = RuntimeError(f"HTTP {e.code}: {detail}")
            if e.code < 500:
                break
        except Exception as e:  # noqa: BLE001
            last = e
        time.sleep(2)
    raise last  # type: ignore[misc]


def mp3_seconds(data: bytes) -> float:
    """纯标准库解析 MP3 帧头求时长（用于章节时间戳），不依赖 ffprobe。"""
    i, total = 0, 0.0
    if data[:3] == b"ID3":
        i = 10 + ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14 | (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
    br_tab = {1: [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320],
              2: [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160]}
    sr_tab = {3: [44100, 48000, 32000], 2: [22050, 24000, 16000], 0: [11025, 12000, 8000]}
    n = len(data)
    while i + 4 <= n:
        if data[i] != 0xFF or (data[i + 1] & 0xE0) != 0xE0:
            i += 1
            continue
        ver = (data[i + 1] >> 3) & 3                             # 3=MPEG1 2=MPEG2 0=MPEG2.5
        layer = (data[i + 1] >> 1) & 3                           # 1=Layer III
        bri, sri, pad = data[i + 2] >> 4, (data[i + 2] >> 2) & 3, (data[i + 2] >> 1) & 1
        if ver == 1 or layer != 1 or bri in (0, 15) or sri == 3:
            i += 1
            continue
        br = br_tab[1 if ver == 3 else 2][bri] * 1000
        sr = sr_tab[ver][sri]
        spf = 1152 if ver == 3 else 576
        flen = (spf // 8) * br // sr + pad
        if flen <= 4:
            i += 1
            continue
        total += spf / sr
        i += flen
    return total


def fmt_ts(sec: float) -> str:
    return f"{int(sec // 60):02d}:{int(sec % 60):02d}"


# ───────────────────────── 主流程 ─────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description="早咖啡 → 通勤收听版")
    ap.add_argument("--md", help="早咖啡 markdown（月度或单日文件）")
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--minutes", type=float, default=0, help="目标时长，默认读 MORNING_BREW_VOICE_MINUTES 或 10")
    ap.add_argument("--no-llm", action="store_true", help="跳过大模型改写，直接用规则稿")
    ap.add_argument("--dry-run", action="store_true", help="不调用任何接口：只产出规则稿 + 规范化结果")
    ap.add_argument("--list-voices", action="store_true", help="列出当前 TTS 模型可用音色")
    args = ap.parse_args()
    load_env()
    OUT.mkdir(exist_ok=True)

    if args.list_voices:
        if not api_key():
            print("✗ 未配置 MORNING_BREW_STEPFUN_API_KEY", file=sys.stderr); return 3
        model = cfg("TTS_MODEL", "stepaudio-2.5-tts")
        print(json.dumps(http_json(f"/audio/system_voices?model={model}", None), ensure_ascii=False, indent=1))
        return 0
    if not args.md:
        ap.error("需要 --md")

    day = args.date
    status_path, md_out, mp3_out = (OUT / f"voice-{day}.json", OUT / f"voice-{day}.md", OUT / f"voice-{day}.mp3")
    status: dict = {"date": day, "status": "failed", "reason": "", "mp3": "", "chapters": [], "checks": {}}

    def finish(code: int) -> int:
        status_path.write_text(json.dumps(status, ensure_ascii=False, indent=1), encoding="utf-8")
        icon = {"ok": "✅", "partial": "⚠️", "dry-run": "📝"}.get(status["status"], "❌")
        print(f"{icon} 语音晨报 {day}：{status['status']}{'｜' + status['reason'] if status['reason'] else ''}")
        print(f"   状态 → {status_path.relative_to(ROOT)}｜播报稿 → {md_out.relative_to(ROOT)}"
              + (f"｜音频 → {mp3_out.relative_to(ROOT)}" if status["mp3"] else ""))
        return code

    md_path = Path(args.md).expanduser()
    if not md_path.exists():
        status["reason"] = f"找不到文件 {md_path}"; return finish(3)
    day_md = extract_day(md_path.read_text(encoding="utf-8"), day)
    if not day_md:
        status["reason"] = f"文件里没有 {day} 的章节"; return finish(3)
    overview, items = parse_items(day_md)
    if not items:
        status["reason"] = "当天章节没有解析到任何条目（检查 ### N. 标题格式）"; return finish(3)

    minutes = args.minutes or float(cfg("VOICE_MINUTES", "10"))
    budget = int(minutes * CHARS_PER_MIN)
    full, brief, dropped = select(items, budget)
    fallback = rule_script(day, overview, full, brief)

    pre_hits: dict = {}
    if args.dry_run or args.no_llm:
        segs, rewrite_note = fallback, "未改写（--dry-run / --no-llm），使用规则稿"
    elif not api_key():
        segs, rewrite_note = fallback, "未配置 API Key，使用规则稿"
    else:
        segs, rewrite_note, pre_hits = llm_script(day, overview, full, brief, budget, fallback)

    # 命中数 = 送模型前的规范化 + 送 TTS 前的规范化（合并统计，质量曲线才不失真）
    words, hits = load_dict(), dict(pre_hits)
    for s in segs:
        s.text = normalize(s.text, words, hits)
    total_chars = sum(len(s.text) for s in segs)
    status["checks"] = {
        "条目": {"解析": len(items), "完整播": len(full), "快讯": len(brief), "未播": len(dropped)},
        "改写": rewrite_note,
        "规范化命中": hits,
        "播报字数": total_chars,
        "预计时长": f"约 {total_chars / CHARS_PER_MIN:.1f} 分钟（目标 {minutes:g}）",
    }

    # ── 合成 ──
    audio, failed, t = bytearray(), [], 0.0
    if args.dry_run:
        status.update(status="dry-run", reason="未调用接口")
        for s in segs:
            status["chapters"].append({"start": "--:--", "title": s.title, "source": s.source})
    elif not api_key():
        status["reason"] = "未配置 MORNING_BREW_STEPFUN_API_KEY，无法合成语音（文字版不受影响）"
    else:
        t0 = time.time()
        for s in segs:
            start = t
            try:
                seg_audio = b"".join(tts(c) for c in chunks(s.text))   # 整段成功才并入，避免章节时间错位
                audio += seg_audio
                t += mp3_seconds(seg_audio)
                status["chapters"].append({"start": fmt_ts(start), "title": s.title, "source": s.source})
            except Exception as e:  # noqa: BLE001
                failed.append(f"{s.title}（{type(e).__name__}: {str(e)[:100]}）")
        status["checks"]["合成耗时"] = f"{time.time() - t0:.0f}s"
        if audio:
            mp3_out.write_bytes(bytes(audio))
            status["mp3"] = str(mp3_out)
            status["checks"]["实际时长"] = fmt_ts(t)
            status["checks"]["文件大小"] = f"{len(audio) / 1e6:.1f} MB"
            status["status"] = "partial" if failed else "ok"
            status["reason"] = ("以下段落合成失败、已跳过：" + "；".join(failed)) if failed else ""
        else:
            status["reason"] = "全部段落合成失败：" + "；".join(failed[:3])

    # ── 播报稿 + 质检记录（给人看，也是抽检错读、补词典的入口）──
    lines = [f"# 语音晨报 · {day}", "",
             f"> 状态：{status['status']}{'｜' + status['reason'] if status['reason'] else ''}", "",
             "## 章节目录", ""]
    lines += [f"- `{c['start']}` {c['title']}" for c in status["chapters"]] or ["- （无音频）"]
    lines += ["", "## 质检记录", "", "```json", json.dumps(status["checks"], ensure_ascii=False, indent=1), "```"]
    if dropped:
        lines += ["", "**本期未播**（超出时长预算，文字版可看）：" + "；".join(i.title for i in dropped)]
    lines += ["", "## 播报稿", ""]
    for s in segs:
        tag = {"llm": "", "rule": "〔规则稿〕", "llm→rule": f"〔回退：{s.note}〕"}[s.source]
        lines += [f"### {s.title} {tag}".rstrip(), "", s.text, ""]
    lines += ["---", "抽检提示：边听边对照播报稿，把读错的词补进 `sources/pronunciation.json`，下期自动生效。"]
    md_out.write_text("\n".join(lines), encoding="utf-8")

    return finish({"ok": 0, "dry-run": 0, "partial": 1}.get(status["status"], 2))


if __name__ == "__main__":
    raise SystemExit(main())
