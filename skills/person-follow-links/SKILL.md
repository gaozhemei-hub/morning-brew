---
name: person-follow-links
description: "Give each person a one-click LinkedIn/X follow link."
version: 0.1.0
author: Zmei_IR, Hermes Agent
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [linkedin, networking, knowledge-base, obsidian]
    related_skills: [opensource-implementation-scout]
---

# 人名 → 一键关注链接（LinkedIn / X）

给知识库里每个人配一个**一次点击就能去关注**的入口。**宁缺勿错**：证据不足就给搜索链接，绝不硬塞一个可能错的人。

## When to Use

- 早咖啡/雷达当天出现新人物，需要建卡并且卡片要带关注入口
- 用户说“点一下就能去关注”/“看不到跳转”
- 批量给一批姓名（+公司）补领英主页
- **不用于**：自动关注/自动发送连接请求（有账号风险，且那是用户的动作，只能给链接）

## Prerequisites

- 脚本：`./scripts/linkedin_match.py`
- 零成本路线：用 Hermes 自带的 `web_search` 跑 `site:linkedin.com/in "姓名" "公司"`（**不要花钱买 Apify/Captain Data 之类的 API**，实测命中率已足够）
- 浏览器登录态（`opencli linkedin people-search`）会消耗月度商业用途额度，**非必要不用**

## Procedure

1. **准备（姓名, 公司/机构）对**。公司名是消歧的关键，缺了它重名率很高。
2. **跑匹配器**（在 `execute_code` 里）：
   ```python
   import sys, os
   sys.path.insert(0, os.path.expanduser("./scripts"))
   from linkedin_match import match_many, render_links_line
   rows = match_many([("Yann LeCun", "AMI Labs"), ("Jensen Huang", "NVIDIA")])
   for r in rows: print(r["confidence"], r["best"], r["reason"])
   ```
   完成标准：每个人拿到 `confidence ∈ 高/中/低` 与理由。
3. **只采信高/中**：
   - **高** → 写个人主页
   - **中** → 写主页但标「（待核）」
   - **低** → **只给搜索链接**，并写清为什么低（如“只有首条证据”“slug 与姓名无关”）
4. **写进卡片**：每张卡最后一行必须是
   ```
   - **关注入口**：LinkedIn → <主页或搜索链接> ｜ 搜索兜底 → <搜索链接>
   ```
   用 `render_links_line(row)` 直接生成，避免手写错。X 方面：**已核实的 handle 用主页**（如 `x.com/karpathy`），未核实的一律搜索链接。
5. **自检**：随机抽 1–2 个“高”置信度链接，用 `web_extract`/浏览器打开确认页面姓名与公司对得上。**对不上就降级为搜索链接。**

## 打分规则（脚本内置，改动就改脚本）

| 信号 | 分值 |
| --- | --- |
| 摘要/标题里出现机构名 | **+3** |
| slug 就是姓名（如 `yann-lecun`） | +2 |
| 是搜索首条 | +1 |
| slug 与姓名毫无关系 | **-3** |

`≥4` → 高｜`=3` → 中｜`<3` → 低。

## Pitfalls

- **搜索引擎会把无关人塞进结果**（尤其名校/大厂同名人），所以“首条”只能算 +1，**机构证据才值 +3**。
- **LinkedIn 主页 URL 会变**（用户改 slug）；链接失效时降级为搜索链接，不要反复猜。
- **重名是常态**：没有公司名时，直接给搜索链接，别赌。
- **不要自动关注**：所有自动连接/关注的尝试都有封号风险，而且用途也不对。
- 中文名的英文拼写不确定时，**两种拼法都试**（如 “Yuandong Tian” 与 “Tian Yuandong”）。

## Verification

- [ ] 每张新卡都有「关注入口」行，且低置信度没有假装成主页
- [ ] 至少抽检 1 个主页，姓名+公司对得上
- [ ] 没有把付费 API 当作前置依赖（能免费跑通）
