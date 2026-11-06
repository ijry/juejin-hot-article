#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score a draft article for Juejin hot-article potential (0-100).

Usage:
    python score_article.py draft.md
    python score_article.py draft.md --title "备选标题" --title-only
    python score_article.py draft.md --json

Thresholds come from the 2026-11-06 study of 50 hot-board articles and
30 long-term collect-board articles (see references/research-report.md).
Standard library only.
"""

import argparse
import json
import re
import sys

HOT_WORDS = ["AI", "Agent", "DeepSeek", "Codex", "Claude", "Skill", "RAG", "MCP",
             "LLM", "GPT", "Vue", "Flutter", "React", "Cursor", "Harness",
             "大模型", "开源", "GitHub", "前端", "后端", "面试", "Android", "iOS"]
HOOK_PAT = r"[?？]|为什么|到底|居然|其实|不是|别|不必|反而|真相|误区|踩|坑|我|亲测|实测|昨晚|刚刚|正式|发布|省|免费|干掉|不用|只"
BANNED = ["全网第一", "震惊", "必看", "万字长文", "史上最全", "不看后悔"]
AI_CLICHE = ["随着", "在当今", "众所周知", "综上所述", "本文将带你", "极大地提升了",
             "希望能帮助到大家", "首先，我们", "总而言之", "值得注意的是"]
BRUSH = ["互赞", "刷阅读", "买阅读", "小号点赞", "互粉", "求赞群"]
# Only unambiguous authoring placeholders. "TODO" / "占位符" are legitimate
# technical terms in real articles and must not trigger false positives.
PLACEHOLDER = ["待补充", "此处填", "待填", "<标题>", "<链接>"]
TAKEAWAY = ["```", "清单", "速查", "模板", "配置", "命令", "复制", "表格", "|"]


def strip_front_matter(text):
    meta = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            block = text[3:end]
            for line in block.splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip().strip('"\'')
            text = text[end + 4:]
    return meta, text


def parse(path, title_override=None):
    with open(path, encoding="utf-8") as f:
        raw = f.read()
    meta, body = strip_front_matter(raw)
    title = title_override or meta.get("title") or ""
    if not title:
        m = re.search(r"^#\s+(.+)$", body, re.M)
        title = m.group(1).strip() if m else ""
    tags = [t.strip() for t in re.split(r"[,，/、\[\]']+", meta.get("tags", "")) if t.strip()]
    return {"title": title, "body": body, "raw": raw, "meta": meta, "tags": tags,
            "path": path}


def score_title(t):
    s, notes = 0, []
    n = len(t)
    if 18 <= n <= 28:
        s += 5
    elif 12 <= n <= 34:
        s += 3; notes.append("标题长度 %d 字，最优区间 18–28 字" % n)
    else:
        notes.append("标题长度 %d 字，过长或过短（样本长尾爆款中位 23 字）" % n)
    if re.search(r"\d", t):
        s += 4
    else:
        notes.append("标题缺具体数字/对象，补一个真实数字")
    if re.search(HOOK_PAT, t):
        s += 4
    else:
        notes.append("标题缺钩子：反常识 / 疑问 / 第一人称实测 / 收益 / 时效")
    if not re.search(r"[：:]", t):
        s += 3
    else:
        notes.append("避免「术语：副标题」结构（3 日榜 38%、收藏榜仅 13.3%）")
    hits = sum(1 for w in HOT_WORDS if w.lower() in t.lower())
    if hits == 1:
        s += 2
    elif hits > 1:
        s += 1; notes.append("热词出现 %d 次，堆砌会稀释信息，保留 1 个" % hits)
    if not any(w in t for w in BANNED):
        s += 2
    else:
        notes.append("标题含空泛夸大词，必须删掉")
    return s, notes


def score_doc(d):
    body, raw, title = d["body"], d["raw"], d["title"]
    notes, detail = [], {}
    plain = re.sub(r"```.*?```", "", body, flags=re.S)
    plain = re.sub(r"[#>*`|\[\]()!-]", "", plain)
    words = len(re.sub(r"\s", "", plain))

    # 选题与可带走产物 15
    s_topic, tn = 0, []
    hw = sum(1 for w in HOT_WORDS if w.lower() in (title + body[:600]).lower())
    if 1 <= hw <= 3:
        s_topic += 4
    elif hw > 3:
        s_topic += 2; tn.append("热词过多，聚焦一个主题")
    else:
        tn.append("未绑定当期热词，曝光面会窄")
    if any(k in raw for k in TAKEAWAY):
        s_topic += 5
    else:
        tn.append("没有可带走的产物：补代码 / 命令 / 配置 / 清单 / 速查表")
    if re.search(r"\d|版本|v\d", title + body[:300]):
        s_topic += 3
    else:
        tn.append("开头缺具体场景或版本")
    if re.search(r"实测|亲测|踩|复现|对照|压测|记录|复盘|教程|步骤", raw):
        s_topic += 3
    else:
        tn.append("看不到实测/教程增量，容易被当成资讯搬运")

    # 结构 25
    s_struct, sn = 0, []
    if 2000 <= words <= 4500:
        s_struct += 6
    elif 1500 <= words <= 6000:
        s_struct += 3; sn.append("正文约 %d 字，建议 2500–3500 字" % words)
    else:
        sn.append("正文约 %d 字，偏离两榜中位（2500 / 3271 字）" % words)
    h2 = len(re.findall(r"^##\s", body, re.M))
    if h2 >= 5:
        s_struct += 5
    elif h2 >= 3:
        s_struct += 3; sn.append("二级标题仅 %d 个，建议 5–8 个编号章节" % h2)
    else:
        sn.append("二级标题仅 %d 个，结构不易扫读" % h2)
    if re.search(r"^##\s*\d|[一二三四五六七八九十]+、", body, re.M):
        s_struct += 3
    else:
        sn.append("章节未编号（样本 56%–66.7% 有编号章节）")
    has_toc = bool(re.search(r"目录|Table of Contents|\[.+\]\(#", body[:1200]))
    if words > 3500 and has_toc:
        s_struct += 2
    elif words <= 3500:
        s_struct += 2
    else:
        sn.append("长文缺目录")
    code = body.count("```") // 2
    if code >= 1:
        s_struct += 3
    else:
        sn.append("缺可运行代码/命令块")
    if re.search(r"!\[|^\s*\|", body, re.M):
        s_struct += 3
    else:
        sn.append("缺图或表格")
    if body.count("**") // 2 + len(re.findall(r"^>\s", body, re.M)) >= 3:
        s_struct += 2
    else:
        sn.append("缺加粗结论/引用块，重点不够跳")
    paras = [len(re.sub(r"\s", "", p)) for p in body.split("\n\n")]
    if max(paras or [0]) <= 400:
        s_struct += 1
    else:
        sn.append("存在超长段落，拆成 2–3 段")

    # 可信度 20
    s_trust, un = 0, []
    first = len(re.findall(r"我|我们|亲测|实测|踩过|复现", body))
    if first >= 3:
        s_trust += 5
    elif first >= 1:
        s_trust += 3; un.append("第一人称实测证据偏少")
    else:
        un.append("没有第一人称实测痕迹，可信度低")
    if len(re.findall(r"\d+(?:\.\d+)?\s*(?:ms|s|秒|%|倍|MB|GB|行|个|次|天|小时)", body)) >= 3:
        s_trust += 4
    else:
        un.append("具体量化数据不足 3 处")
    if re.search(r"边界|不适用|没解决|失败|局限|坑|代价|只在中成立|只在.{0,12}下", body):
        s_trust += 4
    else:
        un.append("缺失败记录 / 边界说明（最容易被误认为 AI 生成）")
    if re.search(r"https?://|参考|官方文档|源码", body):
        s_trust += 3
    else:
        un.append("缺来源/参考链接")
    if re.search(r"版本|v\d|环境|Node|Python|Windows|macOS|Linux", body):
        s_trust += 2
    else:
        un.append("未标注版本/运行环境")
    if not any(p in raw for p in PLACEHOLDER):
        s_trust += 2
    else:
        un.append("仍有占位符/TODO，禁止带占位符发布")

    # 互动设计 10
    s_eng, en = 0, []
    tail = body[-900:]
    if re.search(r"小结|总结|综上|写在最后|结语|结论", tail):
        s_eng += 2
    else:
        en.append("结尾缺总结")
    qs = re.findall(r"[^。\n？?]{10,}[?？]", tail)
    if qs:
        s_eng += 3
    else:
        en.append("结尾缺一个具体可回答的提问（不是「欢迎留言」）")
    if re.search(r"github\.com|仓库|完整配置|复现脚本|源码|文档链接", tail):
        s_eng += 2
    else:
        en.append("结尾缺资源/仓库链接")
    if re.search(r"速查|清单|模板|建议存|可直接复制|收藏", body):
        s_eng += 3
    else:
        en.append("缺收藏钩子：速查表 / 配置模板 / 检查清单")

    # 发布配置 10
    s_pub, pn = 0, []
    if len(d["tags"]) == 3:
        s_pub += 3
    else:
        pn.append("frontmatter 的 tags 需恰好 3 个（1 分类 + 1 技术栈 + 1 热点词）")
    if d["meta"].get("cover"):
        s_pub += 2
    else:
        pn.append("未配置 cover（62% 上榜文章有封面）")
    if re.search(r"原创|首发", raw):
        s_pub += 2
    else:
        pn.append("未声明原创/首发")
    if d["meta"].get("publish_at") or d["meta"].get("publish_time"):
        s_pub += 1
    else:
        pn.append("未记录计划发布时间（建议工作日 08:00–10:00）")
    if d["meta"].get("category"):
        s_pub += 2
    else:
        pn.append("未记录 category")

    # 底线检查
    violations = []
    for w in AI_CLICHE:
        if w in body:
            violations.append("AI 味套话：「%s」" % w)
    for w in BANNED:
        if w in title:
            violations.append("标题夸大词：「%s」" % w)
    for w in BRUSH:
        if w in raw:
            violations.append("疑似引导刷量：「%s」" % w)
    for p in PLACEHOLDER:
        if p in raw:
            violations.append("占位符未清理：「%s」" % p)
    if any(w in title for w in HOT_WORDS) and not any(w in body for w in HOT_WORDS):
        violations.append("标题热词在正文中没有兑现，疑似标题党")

    detail = {"字数": words, "二级标题数": h2, "代码块数": code,
              "标题长度": len(title), "标签数": len(d["tags"])}
    sections = {
        "标题": (score_title(title)[0], 20, score_title(title)[1]),
        "选题与产物": (s_topic, 15, tn),
        "结构": (s_struct, 25, sn),
        "可信度": (s_trust, 20, un),
        "互动设计": (s_eng, 10, en),
        "发布配置": (s_pub, 10, pn),
    }
    total = sum(v[0] for v in sections.values())
    return {"total": total, "sections": sections, "violations": violations,
            "detail": detail, "title": title}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="draft markdown file")
    ap.add_argument("--title", help="override title (useful for comparing candidates)")
    ap.add_argument("--title-only", action="store_true", help="score title only")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    d = parse(args.path, args.title)
    if args.title_only:
        s, notes = score_title(d["title"])
        result = {"title": d["title"], "title_score": s, "max": 20, "notes": notes}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"标题：{d['title']}\n得分：{s}/20")
            for n in notes:
                print("  - " + n)
        return

    r = score_doc(d)
    if args.json:
        print(json.dumps({"total": r["total"], "detail": r["detail"],
                          "sections": {k: {"score": v[0], "max": v[1], "notes": v[2]}
                                       for k, v in r["sections"].items()},
                          "violations": r["violations"]}, ensure_ascii=False, indent=2))
        return

    level = "优秀，可发布" if r["total"] >= 85 else ("达到发布线" if r["total"] >= 75
            else ("需修改后再评" if r["total"] >= 60 else "建议重写"))
    skeleton = r["detail"]["字数"] < 1200
    if skeleton:
        level = "骨架/大纲，正文尚未填充（不可发布）"
    print(f"文件：{d['path']}")
    print(f"标题：{r['title'] or '<未识别>'}")
    if not r["title"]:
        print("提示：请在 frontmatter 写 title: ...，或用 --title 指定标题后重跑")
    print(f"总分：{r['total']}/100  →  {level}\n")
    print(f"{'维度':<12}{'得分':>8}  改进建议")
    print("-" * 72)
    all_notes = []
    for name, (score, mx, notes) in r["sections"].items():
        print(f"{name:<12}{score:>4}/{mx:<4}  {notes[0] if notes else '✓ 达标'}")
        all_notes += ["[%s] %s" % (name, n) for n in notes]
    print("\n稿件概况：" + "，".join(f"{k} {v}" for k, v in r["detail"].items()))
    if r["violations"]:
        print("\n底线检查（必须清零）：")
        for v in r["violations"]:
            print("  ✗ " + v)
    else:
        print("\n底线检查：✓ 未发现套话 / 夸大 / 刷量 / 占位符")
    if all_notes:
        print("\n优先改进项（按影响排序）：")
        for n in all_notes[:8]:
            print("  - " + n)
    if skeleton:
        print("\n结论：正文不足 1200 字，判定为骨架/大纲；填充真实内容后再评分。")
    elif r["total"] < 75:
        print("\n结论：低于 75 分发布线，按上表改完再跑一次本脚本。")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
