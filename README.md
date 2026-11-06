# juejin-hot-article

> 一个符合 [Agent Skills 规范](https://agentskills.io/specification) 的**标准技能**，可被 Codex、Claude Code、WorkBuddy 等支持 Agent Skills 的客户端直接安装。
> 它把「掘金上什么文章更容易热」变成可执行流程：选题 → 标题 → 骨架 → 证据 → 发布配置 → 冷启动 → 发前打分。

[![validate](https://github.com/ijry/juejin-hot-article/actions/workflows/validate.yml/badge.svg)](https://github.com/ijry/juejin-hot-article/actions/workflows/validate.yml)
[![Agent Skills](https://img.shields.io/badge/Agent%20Skills-spec-blue)](https://agentskills.io/specification)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python 3.9+ stdlib only](https://img.shields.io/badge/Python-3.9%2B%20stdlib-informational)

---

## English in 30 seconds

A spec-compliant [Agent Skill](https://agentskills.io/specification) for writing Chinese technical articles that are more likely to reach the [Juejin](https://juejin.cn/) hot board. Built from a measured snapshot of 50 articles on the 3-day hot board, 30 on the 3-month collect board and 7 category boards. The reverse-engineered heat model is `hot_index ≈ 9 × round(views/20 + likes + comments)`. All scripts use the Python standard library only. Install with `npx skills add ijry/juejin-hot-article --skill juejin-hot-article -a codex`.

---

## 为什么是「标准 SKILL」

本仓库不是某个客户端的私有插件，而是一个普通的 Agent Skills 分发仓库：

| 项目 | 说明 |
|---|---|
| 规范 | `agentskills.io` 规范：`SKILL.md` + `name` / `description` 必填 frontmatter |
| 布局 | `skills/<name>/SKILL.md` catalog 布局，`npx skills add <owner>/<repo>` 可自动发现 |
| 可选字段 | 仅使用 `license`、`compatibility`、`metadata`、`allowed-tools` 等规范内字段 |
| 私有字段 | 分发副本**不含** `agent_created` 等客户端专有顶层字段；安装到 WorkBuddy 时由 `install.sh` 本地补上 |
| 依赖 | 三个 Python 脚本只用标准库，无需 pip install |
| 校验 | `scripts/validate_skill.py` 在每次 push 时检查 frontmatter、文件引用、脚本语法与 CSV 完整性 |

---

## 安装

### 方式一：skills CLI（推荐，Codex / Claude Code / Cline / Warp / Zed 等）

```bash
# 交互式：CLI 会列出仓库里发现的 skill 和可选 agent
npx skills add ijry/juejin-hot-article

# 指定 skill 与客户端
npx skills add ijry/juejin-hot-article --skill juejin-hot-article -a codex
npx skills add ijry/juejin-hot-article --skill juejin-hot-article -a claude-code
```

默认安装到当前项目目录；如需全局安装，请按 CLI 的交互提示选择 global scope（或查看 `npx skills add --help`）。

### 方式二：Codex 内置安装器

在 Codex 对话中输入 `$skill-installer`，按提示填写仓库 `ijry/juejin-hot-article`。也可以让 Codex 直接执行：

```
用 $skill-installer 从 ijry/juejin-hot-article 安装 juejin-hot-article 技能
```

### 方式三：仓库自带安装脚本

```bash
git clone https://github.com/ijry/juejin-hot-article.git
cd juejin-hot-article

./install.sh --scope project --agent codex          # 当前项目
./install.sh --scope global  --agent claude-code    # 全局
./install.sh --scope global  --agent all --force    # 一次装到全部客户端
./install.sh --scope project --agent all --dry-run  # 只看会装到哪里
```

支持 `--agent codex|claude-code|workbuddy|all`（可逗号分隔）、`--scope project|global`、`--force`（覆盖前自动备份）、`--no-shim`、`--dry-run`。

### 方式四：手工复制

```bash
mkdir -p ~/.agents/skills
cp -R skills/juejin-hot-article ~/.agents/skills/
```

技能安装目录对照：

| 客户端 | 项目级 | 全局 |
|---|---|---|
| Codex、Cline、Warp、Zed 等 | `.agents/skills/juejin-hot-article/` | `~/.agents/skills/juejin-hot-article/` |
| Claude Code | `.claude/skills/juejin-hot-article/` | `~/.claude/skills/juejin-hot-article/` |
| WorkBuddy | `.workbuddy-ai/skills/juejin-hot-article/` | `~/.workbuddy-ai/skills/juejin-hot-article/` |

### 验证安装

```bash
test -f ~/.agents/skills/juejin-hot-article/SKILL.md && echo OK
python ~/.agents/skills/juejin-hot-article/scripts/score_article.py examples/draft.md
```

在 Codex / Claude Code 里输入：

```
用 juejin-hot-article 帮我写一篇关于 <主题> 的掘金文章，先给 8 个标题候选并逐个打分
```

能返回标题候选和评分表，就说明技能已被加载。

---

## 它能做什么

七步工作流，每一步都有对应的参考文件：

| 步骤 | 动作 | 依据 |
|---|---|---|
| 0 | 确定目标是冲 3 日文章榜、3 月收藏榜还是长期沉淀 | `references/platform-rules.md` |
| 1 | 选题 100 分打分，低于 60 分换题 | `references/platform-rules.md` |
| 2 | 按 10 类公式生成 ≥8 个标题候选并逐项打分 | `references/title-formulas.md` |
| 3 | 从 5 种骨架中选一种，产出编号大纲 | `references/article-templates.md` |
| 4 | 写正文，每节都要留下可带走的产物 | `references/article-templates.md` |
| 5 | 发布时段、标签、封面、冷启动引导互动 | `references/platform-rules.md` |
| 6 | `score_article.py` 发前打分，**低于 75 分不得交付** | `scripts/score_article.py` |
| 7 | 72 小时后复盘互动率；必要时刷新榜单数据 | `scripts/fetch_juejin.py` + `analyze_juejin.py` |

---

## 数据结论（2026-11-06 快照）

| 结论 | 数值 |
|---|---|
| 文章榜热度分 | `hot_index ≈ 9 × round(阅读/20 + 点赞 + 评论)`，50/50 能被 9 整除，48/50 误差 ≤1 |
| 权重换算 | **1 个赞 ≈ 1 条评论 ≈ 20 次阅读**；收藏对文章榜近似 0 权重，但决定收藏榜 |
| 发布时段 | 50 篇样本中 **48%** 在工作日 08:00–10:00 发布 |
| 标题 | 建议 18–28 字、含具体数字、避免「术语：副标题」（3 日榜 38%、收藏榜仅 13.3%） |
| 正文 | 两榜中位字数 2500 / 3271 字；5–8 个编号章节；至少 1 段代码 + 1 张表/图 |
| 标签 | 恰好 3 个 = 1 大分类 + 1 技术栈 + 1 热点词 |
| 封面 | 约 62% 上榜文章有封面 |
| 真实读者信号 | 每千阅读互动数：3 日榜中位 ≈ 20.7，长尾高价值样本 ≈ 34.2 |

完整方法、分布、分类竞争度与局限见 [`skills/juejin-hot-article/references/research-report.md`](skills/juejin-hot-article/references/research-report.md)。

> 热度公式是对单次快照的经验拟合，**不是平台官方披露**。平台算法随时可能调整，请用仓库内的脚本重新抓取验证。

---

## 目录结构

```
juejin-hot-article/
├── README.md                     # 本文件
├── LICENSE                       # MIT
├── CHANGELOG.md
├── CONTRIBUTING.md                # 数据刷新、校验与贡献规范
├── install.sh                     # 一键安装到各客户端
├── .github/workflows/validate.yml # 每次 push 自动校验
├── scripts/
│   └── validate_skill.py          # 规范/引用/语法/CSV 校验（stdlib only）
├── examples/
│   ├── draft.md                   # 真实数据示范稿（可直接打分）
│   ├── prompts.md                 # 常用提示词手册
│   └── cover.svg                  # 示例封面素材
└── skills/
    └── juejin-hot-article/        # ← 标准技能根，安装的就是这个目录
        ├── SKILL.md               # frontmatter + 工作流
        ├── agents/openai.yaml     # Codex / ChatGPT 展示用 metadata（可选）
        ├── references/
        │   ├── research-report.md
        │   ├── title-formulas.md
        │   ├── article-templates.md
        │   ├── platform-rules.md
        │   └── data/{hot_50.csv, collect_30.csv}
        ├── scripts/
        │   ├── score_article.py
        │   ├── fetch_juejin.py
        │   └── analyze_juejin.py
        └── assets/article_skeleton.md
```

---

## 脚本用法

```bash
# 给稿件打分（0–100，逐项建议）
python skills/juejin-hot-article/scripts/score_article.py examples/draft.md

# 只比较标题候选
python skills/juejin-hot-article/scripts/score_article.py examples/draft.md \
  --title "我扒了 50 篇掘金热榜，点赞竟比阅读值钱 20 倍" --title-only

# 刷新掘金榜单数据（需要访问 api.juejin.cn）
python skills/juejin-hot-article/scripts/fetch_juejin.py --out ./snapshot --limit 50
python skills/juejin-hot-article/scripts/analyze_juejin.py --data ./snapshot --out ./snapshot/analysis

# 全仓库校验（CI 同款）
python scripts/validate_skill.py
```

`score_article.py`、`fetch_juejin.py`、`analyze_juejin.py`、`validate_skill.py` 全部只依赖 Python 3.9+ 标准库。

---

## 边界与合规

- 技能内置硬性底线：**不编造数据/案例/截图/benchmark/引用出处**，不写标题党，不引导刷量互赞，技术结论标注版本与环境。
- 仓库只发布逐篇特征 CSV，**不收录第三方文章正文**；原始 API 响应不入库。
- 本仓库与掘金（北京字节跳动科技有限公司）无官方关联，`juejin` 仅用于描述研究对象。
- 数据为 2026-11-06 08:55（UTC+8）单次快照，结论有时效性。

---

## License

[MIT](LICENSE) © 2026 ijry
