---
name: opensource-implementation-scout
description: "Trace how an idea becomes code: repos, README, architecture."
version: 0.1.0
author: Zmei_IR, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [open-source, github, architecture, implementation, radar]
    related_skills: [arxiv]
---

# 开源实现侦察（五道口AI早咖啡 · 第三层）

看“别人怎么把一个想法/论文变成能跑的代码”。这是每日早咖啡的**第三层**，但它是**独立可调用的子 skill**：早报里只给一行摘要，用户看完想深挖时单独跑这个。

## When to Use

- 早报里遇到一个新赛道/新概念（如 AI 视频、GUI Agent、评测框架），想快速知道**实现长什么样**
- 想判断某个能力“能不能自建/能不能用”
- 要写技术选型、面试里要讲“这东西工程上怎么落地”
- **不要用于**：查论文结论（用 `arxiv`）、查行业新闻（用早咖啡主流程）

## Prerequisites

- `terminal` 可用；网络代理 `http://127.0.0.1:7890`（访问 GitHub API 需要时加 `-x`）
- 本地辅助脚本：`./scripts/repo_probe.py`（拉 star 数 + README 结构 + 架构图线索）

## Procedure

1. **定位候选仓库（不要只看第一个）**
   ```bash
   curl -sL -x http://127.0.0.1:7890 \
     "https://api.github.com/search/repositories?q=<英文关键词>&sort=stars&order=desc&per_page=10" \
     | python3 -c "import json,sys;[print(r['stargazers_count'], r['full_name'], '|', (r['description'] or '')[:90]) for r in json.load(sys.stdin)['items']]"
   ```
   完成标准：拿到 **top 5** 的 star 数、仓库名、一句话描述；**star 数要带抓取日期**。

2. **读 README 的“可用边界”**（不是读营销段）
   - 找 `Quick Start` / `Install`：几行能跑起来？
   - 找 `Limitations` / `Not supported` / `Roadmap`：**明确不能做什么**——这一条比“能做什么”重要。
   - 找 benchmark 表：**是自报还是第三方复现**。
   完成标准：能用**一句话**说清“它解决什么、边界在哪”。

3. **找架构图与数据流**（这一层“看实现路径”的核心）
   ```bash
   ls <repo>/docs 2>/dev/null; grep -ilE "architecture|design|pipeline" <repo>/*.md <repo>/docs/*.md 2>/dev/null
   ```
   要找到的：**架构图**（ASCII 也算）/ 模块划分 / 数据从哪流到哪。
   完成标准：能画出**3-5 个方框 + 箭头**的最小结构。

4. **判断维护活跃度（决定能不能用）**
   看 `pushed_at`、近 3 个月提交数、issue 响应、LICENSE（**GPL 有传染性**，商用/开源作品要注意）。
   完成标准：给出“可依赖 / 观望 / 别用”三档之一，并说明理由。

5. **输出四行结论**（这就是交付物，别的都不要写）
   ```
   【实现路径】<赛道>：最热仓库 <owner/repo>（<star>★, <日期>）
   它怎么做：<2 句，点出关键做法>
   边界：<明确做不到什么>｜许可：<LICENSE>｜活跃度：<可依赖/观望/别用>
   对我们的含义：<能不能自建/能不能抄/面试怎么用>｜<URL>
   ```

## Quick Reference

| 需求 | 命令 |
| --- | --- |
| 按关键词找最热仓库 | `api.github.com/search/repositories?q=<kw>&sort=stars` |
| 拉 star + README 结构 + 架构线索 | `python3 ./scripts/repo_probe.py "<关键词>"` |
| 周榜（Python） | `https://mshibanami.github.io/GitHubTrendingRSS/daily/all.xml` |
| Agent 编排共识 | LangChain Blog、LlamaIndex 文档（**每周看一次**） |

## Pitfalls

- **star 数会过期**，必须带抓取日期；旧数当新数引用等于造假。
- **仓库 star 高 ≠ 维护好**（可能弃坑）；但 **GPL 许可**是真的会传染，抄代码前先看 LICENSE。
- **README 的 benchmark 多是自报**，说“官方口径”而不要当事实。
- **别把“找仓库”当交付**：没有“边界 + 许可 + 活跃度”这三样，这一步没做完。

## Verification

- [ ] 每次产出都含：repo + star(带日期) + 关键做法 + **边界** + 许可 + 活跃度 + URL
- [ ] 架构描述能在 5 个方框内说清；说不清说明还没读懂
- [ ] 没有把自报 benchmark 写成客观事实
