# 五道口 AI 早咖啡 · Morning Brew

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg) ![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg) ![Skills](https://img.shields.io/badge/Skills-3-blueviolet.svg) ![Sources](https://img.shields.io/badge/Sources-39%20daily%20%2B%2034%20rotating-informational.svg) ![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)

> 每天早上，用一杯咖啡的时间，把隔夜与昨天的 AI 及相邻行业信息**按三层专业人设筛一遍**，
> 写成一份进 Obsidian、也能发邮件的晨报——并且**自动维护一张会自己长大的知识网**。
>
> **一句话区别**：别人做「信息聚合」，我们做「信息聚合 + 认知沉淀」。

```markdown
# 早咖啡 · 2026-10-12（周一）

## 一、商业与战略层（看钱和壁垒）
### 1. Anthropic 数据中心租赁的账被算出来了 `[必须知道]`
- **核心观点**：①分析师测算单个 245MW 站点年收入约 13 亿美元 ②"租算力"正在变成可被金融建模的资产类别
  ③这解释了为什么这轮 AI 的钱流向电力与土地而不是应用层
- **为什么现在**：当成本结构可以被第三方拆成"每 MW 对应多少收入"，AI 就从"讲故事"进入了可做 DCF 的阶段
- **名词**：[[技术名词库#KV Cache|KV Cache↗]]｜**人物**：[[大佬履历卡#Martin Casado|Martin Casado↗]]
- 来源：<https://www.techmeme.com/261011/p9>（2026-10-11）

## 二、技术与前沿层（看可能性和边界）
### 2. OpenAI 一次放出 722 篇数学论文手稿 `[必须知道]`
- **核心观点**：…（分点）
- **衡量方式**：这类能力的评测不是准确率，而是**可验证性**——能不能被 Lean 形式化检验
…
## 四、今日中文热议（只列榜单，不做解读）
**财联社电报**｜**雪球热股**｜**微博热搜** …
```

---

## 一、为什么做这个（产品起点）

它来自三个真实的痛点，而不是"我想做个爬虫"：

| 痛点 | 现状 | 我们的解法 |
| --- | --- | --- |
| **现成的 AI 总结"太宽泛"** | 商用工具给的是要点堆砌，读完仍不知道"这跟我有什么关系" | **三层人设**：每层由一个明确的专业身份来读，回答该身份真正关心的问题 |
| **刷完就忘，信息不成体系** | 读完 50 条，下周只记得 3 条 | **双链知识网**：术语与人物自动归档，正文可点击跳转，读新闻同时长知识 |
| **大佬不认识，不知道该怎么规划职业** | 只看到名字，看不到路径 | **人物跟踪是一等公民**：自动建卡（现职｜关键转向｜为什么今天出现｜对我的用法）+ 一键关注入口 |

**设计原则（贯穿全部决策）**：**宁缺勿错 · 禁止静默失败 · 先长后精**。

---

## 二、设计决策（为什么这么做，而不是那样做）

这是这个项目最想被看到的部分——**每一个"不用什么"都是刻意的**。

### 1. 为什么是"三层人设"，而不是"关键词 + AI 打分"
关键词过滤解决不了"这条信息对我有什么用"。我们改成**先定义读者身份，再让身份决定筛选标准**：
投资人看"谁在买单"，产品经理看"用什么指标衡量"，工程师看"怎么落地"。
**代价**：无法用单一分数排序；**收益**：产出可以直接用，而不是再读一遍原文。

### 2. 为什么"必须写衡量方式"
技术层的每条都要回答"这件事用什么指标被衡量"。理由：**产品经理的核心能力是定义评测**，
而行业新闻 90% 只讲能力不讲度量。强制这一栏，等于每天训练一次"什么是好的评测口径"。

### 3. 为什么把知识库做成双链，而不是塞进同一个文件
信息是流，知识是网。**术语与人物必须能被复用、被引用、被回看**。
我们用 Obsidian 的 `[[文件#标题|显示名↗]]`：正文里的术语一跳就到术语库，人物一跳就到履历卡。
**给"能不能点"加可视化标记（`↗`）**——这是被真实用户反馈逼出来的设计（"看不到跳转"）。

### 4. 为什么人物跟踪要独立成体系，还带置信度
"在文章里识别人名"容易，**给人配一个正确的主页很难**。
我们做了**二段式消歧 + 置信度打分**：机构名出现在摘要里 +3、slug 就是姓名 +2、搜索首条 +1、slug 与姓名无关 −3。
**≥4 给主页｜=3 给主页并标"待核"｜<3 只给搜索链接**。
**宁缺勿错**：实测 12 人里 10 人判高/中，2 人因证据不足被判低——**这个"拒绝"是设计目标，不是缺陷**。
（独立成 skill：`person-follow-links`）

### 5. 为什么信源健康必须分三类
大多数聚合项目的失败是**静默的**：源挂了，只是"今天少了几条"，没人发现。
我们强制输出：**✅ 有新增 / ⚠️ 抓成功但今天无新 / ❌ 抓失败（含原因）**。
把"源挂了"和"今天没新闻"分开，是**可观测性**的最小要求。

### 6. 为什么信源要"轮换"而不是"全扫"
公众号源多、更新慢、同质化高。全扫只会刷屏，还稀释真正重要的信号。
改成**按星期轮值**（周一 AI前沿、周二 商业创投、周三 产品工程、周四 半导体、周日全扫）：
既保证覆盖面，又让每天的产出有**主题感**。

### 7. 为什么新信源先放"候补"而不是直接加
信源不是越多越好，**是越准越好**。没验证过的源直接进正文，只会降低信噪比。
所以我们把候选源单独放一份《候补信源》，按主题分组、标注可用性，**由用户决定何时升进正式三层**。

### 8. 为什么"早期允许写长"
**先是信息密度，再是精炼**。过早压缩会丢掉推理链和例子；等格式稳定、偏好明确后再收紧。
（这条也写在规范里，作为对贡献者的期待管理）

---

## 三、竞品分析（站在巨人肩膀上）

这个项目**不是从零发明**。我们系统看过同类项目，明确"借什么、不借什么"。

| 项目 | 它的定位 | 我们借用了什么 | 我们的差异 |
| --- | --- | --- | --- |
| **[BestBlogs](https://github.com/ginobefun/BestBlogs)** | 400+ RSS 的内容聚合平台 | ⭐**关键贡献**：它公开维护的 wechat2rss 实例提供 **375 个微信公众号 RSS**，一次打通"中文源" | 我们只取"源"，不复制其产品形态 |
| **[TrendRadar](https://github.com/sansan0/TrendRadar)**（62.8k★） | 11+ 平台热榜聚合 + 推送 | 中文热榜走第三方 API 而非自建爬虫的思路；增量式幂等去重 | 热榜只是我们的**第四块**，不是主体；我们做的是"认知沉淀" |
| **[Horizon](https://github.com/Thysrael/Horizon)**（9.6k★） | 每日 AI 资讯自动摘要 | 单 JSON 管全部信源；Fetch→去重→打分→筛选→投递的流水线骨架 | 我们加了**人设分层**与**知识库双链**（它输出纯 markdown） |
| **[ai-news-brief](https://github.com/frankzch/ai-news-brief)** | 94 源 + 双语摘要 | 两阶段去重（指纹粗筛 → 语义精筛）、分层反爬 | 我们暂未上向量去重（信源规模还不够大） |
| **[ai-daily-pulse](https://github.com/FavorPan/ai-daily-pulse)** | RSS → 打分 → Obsidian 日报 | 反幻觉思路（事实 token 对齐）；RSS 正文过短时回退抓全文 | **它的输出是 Obsidian 日报，但用普通 markdown；双链与人物库是我们独有的** |
| **[news-summary](https://github.com/guo-yichen/news-summary)** | RSS → Notion/邮件 | ⭐**"no updates today" 显式列出**——信源沉默失败可观测，我们从它学的最有用一条 | 我们扩成三类健康状态 |
| **[Awesome-AISourceHub](https://github.com/AmbroseX/Awesome-AISourceHub)** | 分平台信息源清单 | 源清单与质量标注（已存档到本仓库） | 我们只把它当**候选池**，验证后才进正式源 |
| **[RSSHub](https://github.com/DIYgod/RSSHub)**（46k★） | 万物皆可 RSS | 无 RSS 站点的通用兜底（36氪即走此路） | 我们把它当工具，不重复造 |
| Folo / FreshRSS / n8n | 阅读器与自动化 | 结论：**这两层直接用现成的**，不必自建 | 我们只做上层（分层、沉淀、投递） |

### 我们的生态位

- **大多数项目**：把信息**送到你眼前**（聚合 + 摘要 + 推送）
- **少数项目**：把信息**总结得更好**（LLM 摘要 + 打分）
- **我们**：把信息**变成你的资产**——术语进库、人物进卡、每条可追溯、每期有健康报告

> 一句话生态位：**别人优化"读什么"，我们优化"读完留下什么"。**

---

## 四、快速开始

```bash
git clone <this-repo> && cd morning-brew
cp .env.example .env          # ← 把里面的邮箱换成你自己的（provider=none 时也可先不发信）

python3 scripts/fetch.py --days 2 --rotate AI前沿     # 抓取（周一加 --weekly）
python3 scripts/digest_brief.py --health              # 看信源健康
python3 scripts/hotlist.py --per 5                    # 第四块·中文热议
python3 scripts/setup_email.py                        # （可选）一键配邮箱，交互式
```

**必须替换的配置**（别人拿到项目第一件事）：

```ini
MORNING_BREW_EMAIL_PROVIDER=none          # none | qq | gmail | smtp
MORNING_BREW_EMAIL_TO=you@example.com     # ← 换成你的收件邮箱
MORNING_BREW_SMTP_PASS=                   # QQ 授权码 / Gmail 应用专用密码（不是登录密码）
# MORNING_BREW_PROXY=http://127.0.0.1:7890   # 需要访问海外源时
```

## 四·五、定时运行（**时间可自定义**）

**默认每天 07:30**。改时间只要一条命令（会自动写好定时任务，幂等）：

```bash
python3 scripts/install_schedule.py --at 08:40 --install   # 写入系统 crontab
python3 scripts/install_schedule.py --show                 # 看当前设的时间
python3 scripts/install_schedule.py --at 08:40             # 只打印安装方式（不写系统）
```

- **系统 crontab**：任何 macOS/Linux 都能用（推荐）
- **Agent 定时任务**（如 Hermes）：新建一个每日任务，让它跑 `python3 scripts/daily.py`，时间设为你要的即可（提示词参考 `skills/morning-brew/SKILL.md`）

⚠️ **一个必须知道的坑：macOS 合盖会睡眠，任务不会按时跑。**
三种解法：① 插电 + 外接显示器（clamshell）；② `sudo pmset -a disablesleep 1`（合盖不睡，注意散热）；
③ 把时间设在你一定会开机的时段（例如起床后 08:40）。

## 四·六、信源构成（口径以 `sources/sources.json` 为准）

`sources` 数组共 **77 条记录 = 39 常驻 + 34 轮换 + 4 不可用**（恒等可自查）：

| 类别 | 数量 | 明细 |
| --- | --- | --- |
| **常驻源**（每天都抓） | **39** | 海外 VC／科技媒体（Sequoia、a16z、Techmeme…）+ 中文媒体 + 论文与产品榜（HF Daily Papers、Product Hunt）+ GitHub Trending + 已接入的 3 个公众号（硅星人Pro、42章经、饭统戴老板），每条带 `verified` 实测结论 |
| **轮换公众号**（按星期轮值） | **34** | **AI前沿 9**（周一/周五）｜**商业创投 12**（周二/周六）｜**产品工程 11**（周三）｜**半导体 2**（周四）｜周日全扫。轮换表以 `scripts/daily.py` 的 `ROTATION` 为唯一准绳 |
| **不可用**（已记录，不抓） | **4** | Benchmark（无内容源）｜峰瑞资本（无可用源）｜微信公众号源：东四十条资本 / 融了么（不在公开实例中）｜LlamaIndex 文档（改由「开源与工程层」子 skill 每周检查） |
| **公众号候选池** | **375** | 来自 [BestBlogs](https://github.com/ginobefun/BestBlogs) 公开维护的 wechat2rss 实例（见 `sources/wechat-bestblogs-375.opml`）。**候选池 ≠ 已采用**：目前从中接入 **37 个**（3 常驻 + 34 轮换），其余仍是候选，验证后才进正式源 |
| **中文热榜**（第四块） | **8** | 财联社电报、华尔街见闻、雪球热股、Hacker News、V2EX、少数派、微博热搜、知乎热榜（见 `scripts/hotlist.py`；无需 API key） |


> **已知中文源缺口（9 个）**：量子位、投中网、深响、瑞泽洞察、融了么、东四十条资本、GGV纪源资本、AI闹、葬AI
> ——均不在 BestBlogs 公开实例的 375 源中，需自建 wechat2rss 实例才能补上（另有峰瑞资本在候选池中但源不可用）。
> **这一行是刻意写出来的**：缺口被点名，才有可能被补上。

> **为什么强调口径**：信源数量是这类项目最容易含糊的地方。上表的每个数字都能用
> `python3 -c "import json;d=json.load(open('sources/sources.json'));print(len(d['sources']))"` 与 `scripts/daily.py --help` 自行复核。

## 五、项目结构

```
skills/                      ← 核心：以 skill 组织，可直接装进支持 skills 的 agent
  morning-brew/              ★ 主 skill：三层人设 + 输出规范 + 完整流程 + 踩坑
  person-follow-links/       人名 → 一键关注链接（带置信度打分，宁缺勿错）
  opensource-implementation-scout/  论文/想法 → 代码：找仓库、读边界、看架构
scripts/
  fetch.py                   多类型抓取（rss / json_api / html / sitemap / hf_daily / twitter）+ 轮换
  digest_brief.py            抓取结果 → 人/模型可读简报 + 信源健康
  hotlist.py                 第四块·中文热议（8 个榜，无需 API key）
  send_digest.py             markdown → HTML 邮件，provider 可切换
  setup_email.py             交互式配邮箱（授权码隐藏输入，不落聊天记录）
  linkedin_match.py          人名 → 领英主页（置信度打分）
  repo_probe.py              仓库 star / README 结构 / 架构图线索
sources/
  sources.json               信源清单（每条带 verified 实测结论与日期）
  wechat-bestblogs-375.opml  375 个微信公众号源（来自 BestBlogs，致谢）
templates/                   深挖档案 / 价值链地图模板
docs/                        规范、迭代记录、踩坑清单
examples/                    产出示例（含"手写基准版"）
```

## 六、迭代史（过程材料都在 `docs/` 与 `examples/`）

| 版本 | 触发 | 关键改动 |
| --- | --- | --- |
| **v0** 通用资讯雷达 | "帮我每天看前沿" | 21 个源、一句话判断式条目 |
| **v1** 用户判定不合格 | 用户指出"太宽泛、没有层次" | 用户给出一份完整指引 → 确定**三层结构 + 每层人设 + 指定信源** |
| **v2** 双链与人物库 | 用户反馈"看不到跳转""大佬不认识" | 知识库标题规范化做锚点；正文双链加 `↗`；人物卡加**一键关注** |
| **v3** 信源扩容（可用源 21 → 73） | 用户提示"GitHub 上肯定有人做过" | 抄现成：接入 375 候选池中的 37 个公众号源（推翻"只能自建"的旧结论）、新增热榜第四块、轮换组按星期轮值。**按今天的口径：常驻 39 + 轮换 34 = 73 个可用源** |
| **v4** 工程加固 | 定时任务实测暴露问题 | 修复去重键丢查询参数、轮换判断顺序、`.env` 优先级、邮件引用块渲染 |

**两份过程材料值得单独看**：
- [`docs/规范-五道口AI早咖啡.md`](docs/规范-五道口AI早咖啡.md) —— **用户在 v1 手写的完整设计指引**，是本项目的"需求文档"
- [`examples/样例-手写基准-2026-10-12.md`](examples/样例-手写基准-2026-10-12.md) —— 人工写出的**基准样例**，用来校准机器输出的水准

**这份迭代史本身就是产品方法论的演示**：先跑通最小闭环 → 用真实反馈定标准 → 再扩源 → 最后工程加固。

## 七、踩坑清单（给下一个用的人省一天）

1. **HTML 源去重键不能砍查询参数** —— `?id=1848`、`?id=1792` 会塌缩成一条，整站只剩 1 条（甲子光年 44→1、晚点 11→1 都栽在这）。
2. **相对链接要无条件 `urljoin`**，别写 `if url.startswith("/")`（`./x?id=1` 不满足）。
3. **`ssl` 的 HTTPSHandler 必须在 `build_opener` 之前传入**，否则会被默认 handler 抢先，`insecure` 静默失效。
4. **原生 RSS 会悄悄下线**（a16z 的 `/feed` 全 404，只剩 sitemap）；所以要监控信源健康。
5. **sitemap 常是两级**（index → post-sitemap），且顺序多为旧→新，要倒序取最新。
6. **列表页可能是 JS 渲染**：HTML 里没有文章链接时，去试它的 REST API（如 WordPress `/wp-json/wp/v2/posts`）。
7. **SPA 站点的真列表入口常不在首页**（晚点首页 1 条，`/site/index` 有 11 条）。
8. **cron 环境会拦截内联 python 与 heredoc** —— 取数逻辑必须落在脚本文件里。
9. **配置文件要对外部环境变量有最终解释权**：持久 shell 里残留的空 `SMTP_PASS` 会盖住 `.env` 里的真授权码，报"配置不完整"。
10. **邮件渲染要处理引用块与分隔线**，改完**必须真发一封到目标邮箱验证**，dry-run 只证明字符串变了。
11. **"做不到"的结论先去 GitHub 复检**：公众号曾判定"只能自建、每 80 小时扫码"，实际有公开实例可直连。

## 八、致谢

感谢 [BestBlogs](https://github.com/ginobefun/BestBlogs)（公众号源）、[TrendRadar](https://github.com/sansan0/TrendRadar)、
[Horizon](https://github.com/Thysrael/Horizon)、[ai-daily-pulse](https://github.com/FavorPan/ai-daily-pulse)、
[ai-news-brief](https://github.com/frankzch/ai-news-brief)、[news-summary](https://github.com/guo-yichen/news-summary)、
[Awesome-AISourceHub](https://github.com/AmbroseX/Awesome-AISourceHub)、[RSSHub](https://github.com/DIYgod/RSSHub)、
[newsnow](https://github.com/ourongxing/newsnow) 等先行项目——**没有它们，这个项目不会在两周内成形。**

## License

MIT（见 `LICENSE`）。信源内容版权归原站所有，本项目只做聚合与摘要、**不转载正文**。
请遵守各站点 robots 与使用条款；公众号源依赖第三方公开实例，请自行评估合规性。
