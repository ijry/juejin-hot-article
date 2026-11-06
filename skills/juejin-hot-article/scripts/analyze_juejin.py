#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Quantify what makes Juejin articles hot.

Reads the JSON produced by fetch_juejin.py and emits:
    analysis/stats.json      all computed statistics (machine readable)
    analysis/findings.md     human-readable statistical summary
    analysis/hot_50.csv      per-article feature table (main sample)
    analysis/collect_30.csv  per-article feature table (long-term value sample)

Usage:
    python analyze_juejin.py --data ./data --out ./analysis
"""

import argparse
import csv
import json
import os
import re
import statistics as st
from collections import Counter
from datetime import datetime

# ---------------------------------------------------------------- feature sets
HOT_TECH = ["AI", "Agent", "DeepSeek", "Codex", "Claude", "Skill", "RAG",
            "MCP", "LLM", "GPT", "Vue", "Flutter", "React", "Cursor", "Harness",
            "WorkBuddy", "大模型", "开源", "GitHub", "面试", "前端", "后端"]
HEAD_PATTERNS = {
    "结论先行": ["先说结论", "结论是", "先说", "一句话", "总的来说"],
    "背景铺垫": ["最近", "上周", "昨天", "今天", "前言", "背景", "写在前面", "大家好", "一直以来"],
    "提问开场": ["？", "?", "为什么", "怎么", "如何"],
    "数据开场": [r"\d+%", r"\d+ 万", r"\d+万", r"\d+ 个", r"\d+个"],
}
TAIL_PATTERNS = {
    "总结收尾": ["总结", "综上", "最后", "写在最后", "结语", "小结"],
    "互动引导": ["评论", "点赞", "收藏", "关注", "欢迎", "留言", "一起讨论"],
    "资源链接": ["github.com", "仓库", "源码", "参考链接", "官方文档", "地址"],
}


def pct(n, d):
    return round(100.0 * n / d, 1) if d else 0.0


def q(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return 0
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (k - lo), 1)


def describe(vals):
    vals = [float(v) for v in vals if v is not None]
    if not vals:
        return {}
    return {"min": min(vals), "p25": q(vals, .25), "median": round(st.median(vals), 2),
            "mean": round(st.mean(vals), 2), "p75": q(vals, .75), "max": max(vals)}


def title_features(t):
    t = t or ""
    num = bool(re.search(r"\d", t))
    return {
        "title_len": len(t),
        "has_number": num,
        "is_question": bool(re.search(r"[?？]|吗\b|为什么|凭什么|是不是|该如何|怎么办", t)),
        "has_exclaim": bool(re.search(r"[!！]", t)),
        "has_colon": bool(re.search(r"[：:|｜·—]", t)),
        "first_person": bool(re.search(r"我|咱|自己", t)),
        "second_person": bool(re.search(r"你|你们", t)),
        "list_signal": bool(num and re.search(r"个|款|步|条|张|招|组|种|大|点|坑|款|篇|万|张图|行", t)),
        "contrast": bool(re.search(r"为什么|居然|竟|其实|不是|别|不必|反而|真相|误区|错|被吹|骗局|难|坑|踩|翻车|崩|谁|到底|并不|没有|只|却", t)),
        "authority": bool(re.search(r"最|第一|全网|独家|官方|正式|发布|首发|开源|大厂|一线|权威|指南|规范|最佳实践|保姆级|万字|必装|值得", t)),
        "tutorial": bool(re.search(r"实战|教程|保姆级|手把手|从零|指南|实践|复盘|原理|源码|拆解|剖析|详解|流程|方案|总结|笔记|闭环|策略|机制|设计|优化|适配|修复", t)),
        "benefit": bool(re.search(r"省|快|免费|效率|赚|提效|避坑|白嫖|不花|一键|秒|轻松|爽|强|好用|能用|值得|够用", t)),
        "time_hook": bool(re.search(r"今天|昨晚|刚刚|来了|新版|发布|速报|周报|趋势|20\d\d|正式|开源了|崩了|上线", t)),
        "has_emoji": bool(re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", t)),
        "hot_tech": bool(re.search("|".join(re.escape(w) for w in HOT_TECH), t, re.I)),
        "personal_test": bool(re.search(r"我|亲测|实测|踩过|试了|用了|做完|抓包|复盘|记录|上线了|做了个|我用", t)),
        "series": bool(re.search(r"第\s*\d+\s*[期篇]|#\d+|系列|周报|速报|日报", t)),
    }


def body_features(md):
    md = md or ""
    lines = md.splitlines()
    head = "\n".join(lines[:12])[:300]
    tail = "\n".join(lines[-15:])[-400:]
    out = {
        "headings": sum(1 for l in lines if re.match(r"^#{1,6}\s", l)),
        "h2plus": sum(1 for l in lines if re.match(r"^#{2,3}\s", l)),
        "code_blocks": md.count("```") // 2,
        "images": len(re.findall(r"!\[[^\]]*\]\(", md)),
        "links": len(re.findall(r"\[[^\]]+\]\(https?://", md)),
        "table_rows": sum(1 for l in lines if re.match(r"^\s*\|", l)),
        "bold_spans": md.count("**") // 2,
        "ordered_sections": bool(re.search(r"[一二三四五六七八九十]+、|^\s*##\s*\d", md, re.M)),
        "has_toc": bool(re.search(r"目录|Table of Contents|\[.*\]\(#", md[:1200])),
    }
    for name, pats in HEAD_PATTERNS.items():
        out["open_" + name] = any((re.search(p, head) if p.startswith("\\") else p in head) for p in pats)
    for name, pats in TAIL_PATTERNS.items():
        out["end_" + name] = any(p.lower() in tail.lower() for p in pats)
    return out


def solve_ols(X, y):
    """Least squares via normal equations + Gaussian elimination (stdlib only)."""
    n = len(X[0])
    A = [[sum(row[i] * row[j] for row in X) for j in range(n)] +
         [sum(row[i] * yi for row, yi in zip(X, y))] for i in range(n)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(A[r][col]))
        A[col], A[pivot] = A[pivot], A[col]
        if abs(A[col][col]) < 1e-9:
            continue
        div = A[col][col]
        A[col] = [v / div for v in A[col]]
        for r in range(n):
            if r != col:
                f = A[r][col]
                A[r] = [a - f * b for a, b in zip(A[r], A[col])]
    return [A[i][-1] for i in range(n)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="./data")
    ap.add_argument("--out", default="./analysis")
    args = ap.parse_args()
    data, out = os.path.abspath(args.data), os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    with open(os.path.join(data, "articles.json"), encoding="utf-8") as f:
        hot = json.load(f)
    with open(os.path.join(data, "articles_collect.json"), encoding="utf-8") as f:
        collect = json.load(f)

    # enrichment
    for group in (hot, collect):
        for r in group:
            r.update(title_features(r["title"]))
            r.update(body_features(r["markdown"]))
            v = max(int(r["view"] or 0), 1)
            r["engage_per_1k"] = round(1000 * (int(r["like"] or 0) + int(r["collect"] or 0)
                                               + int(r["comment"] or 0)) / v, 2)
            r["like_rate"] = round(100 * int(r["like"] or 0) / v, 3)
            r["collect_rate"] = round(100 * int(r["collect"] or 0) / v, 3)
            r["comment_rate"] = round(100 * int(r["comment"] or 0) / v, 3)
            try:
                dt = datetime.fromisoformat(r["published_at"])
                r["publish_hour"] = dt.hour
                r["publish_weekday"] = dt.weekday()
            except (ValueError, TypeError):
                r["publish_hour"] = r["publish_weekday"] = None

    numeric = ["view", "like", "collect", "comment", "hot_rank", "age_hours_at_fetch",
               "content_count", "title_len", "tag_count", "engage_per_1k",
               "like_rate", "collect_rate", "comment_rate", "headings", "code_blocks",
               "images", "links", "table_rows", "catalog_count"]
    bool_keys = [k for k, v in title_features("").items() if isinstance(v, bool)]
    bool_keys += [k for k in body_features("").keys() if k.startswith("open_") or k.startswith("end_")]
    bool_keys += ["has_toc", "ordered_sections", "has_cover", "is_original"]

    def profile(group):
        p = {k: describe([r.get(k) for r in group]) for k in numeric}
        p["bool_rates"] = {k: pct(sum(1 for r in group if r.get(k)), len(group)) for k in bool_keys}
        p["categories"] = dict(Counter(r["category"] for r in group).most_common())
        p["tags"] = dict(Counter(t for r in group for t in r["tags"]).most_common(25))
        p["publish_hours"] = dict(sorted(Counter(r["publish_hour"] for r in group
                                                 if r["publish_hour"] is not None).items()))
        p["publish_weekdays"] = dict(sorted(Counter(r["publish_weekday"] for r in group
                                                    if r["publish_weekday"] is not None).items()))
        p["authors"] = dict(Counter(r["author"] for r in group).most_common(10))
        p["read_time"] = dict(Counter(r["read_time"] for r in group).most_common(12))
        return p

    hot_p, col_p = profile(hot), profile(collect)

    # heat-model regression on the 3-day board
    X = [[float(r["view"] or 0), float(r["like"] or 0), float(r["collect"] or 0),
          float(r["comment"] or 0), float(r["age_hours_at_fetch"] or 0)] for r in hot]
    y = [float(r["hot_rank"] or 0) for r in hot]
    coef = solve_ols(X, y)
    pred = [sum(c * v for c, v in zip(coef, row)) for row in X]
    ybar = st.mean(y)
    r2 = 1 - sum((a - b) ** 2 for a, b in zip(y, pred)) / max(sum((a - ybar) ** 2 for a in y), 1e-9)
    heat_model = {"coefficients": dict(zip(["view", "like", "collect", "comment", "age_hours"],
                                           [round(c, 4) for c in coef])),
                  "r2": round(r2, 4),
                  "hot_per_view_ratio": describe([1000 * r["hot_rank"] / max(r["view"], 1) for r in hot])}

    # category competition: entry thresholds from per-category boards
    cats = {}
    for fn in sorted(os.listdir(data)):
        if not fn.startswith("rank_category_"):
            continue
        with open(os.path.join(data, fn), encoding="utf-8") as f:
            rows = json.load(f)
        name = fn.replace("rank_category_", "").replace(".json", "")
        ranks = [x["content_counter"]["hot_rank"] for x in rows]
        views = [x["content_counter"]["view"] for x in rows]
        cats[name] = {"count": len(rows), "top_heat": max(ranks) if ranks else 0,
                      "median_heat": round(st.median(ranks), 1) if ranks else 0,
                      "entry_heat": min(ranks) if ranks else 0,
                      "median_view": round(st.median(views), 1) if views else 0,
                      "top_title": rows[0]["content"]["title"] if rows else ""}
    name_map = {"6809637769959178254": "后端", "6809637767543259144": "前端",
                "6809635626879549454": "客户端", "6809637773935378440": "人工智能",
                "6809637771511070734": "开发工具", "6809637776263217160": "代码人生",
                "6809637772874219534": "阅读"}
    cats = {name_map.get(k, k): v for k, v in cats.items()}

    # comparison deltas of title tactics
    deltas = {}
    for k in bool_keys:
        a, b = hot_p["bool_rates"].get(k, 0), col_p["bool_rates"].get(k, 0)
        deltas[k] = {"hot3d": a, "collect3m": b, "delta": round(b - a, 1)}
    deltas = dict(sorted(deltas.items(), key=lambda kv: -abs(kv[1]["delta"])))

    # top engagement-rate articles among the long-term sample
    value_leaders = [{"rank": r["rank"], "title": r["title"], "view": r["view"],
                      "like": r["like"], "collect": r["collect"], "comment": r["comment"],
                      "engage_per_1k": r["engage_per_1k"], "content_count": r["content_count"]}
                     for r in sorted(collect, key=lambda r: -r["engage_per_1k"])[:12]]

    stats = {"sample": {"hot_3d": len(hot), "collect_3m": len(collect),
                        "fetched_at": json.load(open(os.path.join(data, "fetch_summary.json"),
                                                     encoding="utf-8"))["fetched_at"]},
             "hot_profile": hot_p, "collect_profile": col_p,
             "heat_model": heat_model, "category_boards": cats,
             "feature_deltas": deltas, "value_leaders": value_leaders,
             "hot_titles": [r["title"] for r in hot],
             "collect_titles": [r["title"] for r in collect]}

    with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    # CSV feature tables
    columns = ["rank", "title", "author", "category", "tags", "published_at", "age_hours_at_fetch",
               "view", "like", "collect", "comment", "hot_rank", "engage_per_1k",
               "content_count", "read_time", "title_len", "tag_count", "has_cover",
               "has_number", "is_question", "first_person", "contrast", "authority",
               "tutorial", "benefit", "time_hook", "hot_tech", "personal_test", "series",
               "headings", "code_blocks", "images", "links", "has_toc",
               "open_结论先行", "open_背景铺垫", "open_提问开场", "end_总结收尾",
               "end_互动引导", "end_资源链接", "url"]
    for fname, group in (("hot_50.csv", hot), ("collect_30.csv", collect)):
        with open(os.path.join(out, fname), "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            w.writeheader()
            for r in group:
                row = dict(r)
                row["tags"] = " / ".join(r["tags"])
                w.writerow(row)

    # readable findings
    L = []
    L.append("# 掘金热榜量化分析（自动生成）\n")
    L.append(f"样本：3 日文章榜 {len(hot)} 篇 / 3 月收藏榜 {len(collect)} 篇；"
             f"抓取时间 {stats['sample']['fetched_at']}\n")
    L.append("## 1. 两组样本的量级差异（关键：绝对数不是同一量级）\n")
    L.append("| 指标 | 3 日热榜 中位数 | 3 月收藏榜 中位数 |")
    L.append("|---|---:|---:|")
    for k in ["view", "like", "collect", "comment", "content_count", "title_len", "engage_per_1k"]:
        L.append(f"| {k} | {hot_p[k]['median']} | {col_p[k]['median']} |")
    L.append("\n## 2. 热度公式拟合（3 日榜）\n")
    L.append("```json\n" + json.dumps(heat_model, ensure_ascii=False, indent=2) + "\n```\n")
    L.append("## 3. 标题战术出现率对比（%）\n")
    L.append("| 特征 | 3 日热榜 | 3 月收藏榜 | 差值(收藏-热榜) |")
    L.append("|---|---:|---:|---:|")
    for k, v in list(deltas.items())[:24]:
        L.append(f"| {k} | {v['hot3d']} | {v['collect3m']} | {v['delta']:+} |")
    L.append("\n## 4. 3 日热榜关键分布\n")
    for k in ["view", "hot_rank", "age_hours_at_fetch", "content_count", "title_len",
              "tag_count", "engage_per_1k"]:
        L.append(f"- {k}: {hot_p[k]}")
    L.append(f"- 分类分布: {hot_p['categories']}")
    L.append(f"- 高频标签: {list(hot_p['tags'].items())[:15]}")
    L.append(f"- 发布时段(小时): {hot_p['publish_hours']}")
    L.append(f"- 正文结构命中率: " + json.dumps({k: v for k, v in hot_p['bool_rates'].items()
                                              if k.startswith(('open_', 'end_', 'has_toc', 'ordered'))},
                                             ensure_ascii=False))
    L.append("\n## 5. 分类榜进入门槛\n")
    L.append("| 分类 | 榜首热度 | 中位热度 | 末位热度(门槛) | 中位阅读 | 榜首标题 |")
    L.append("|---|---:|---:|---:|---:|---|")
    for k, v in sorted(cats.items(), key=lambda kv: -kv[1]["median_heat"]):
        L.append(f"| {k} | {v['top_heat']} | {v['median_heat']} | {v['entry_heat']} | "
                 f"{v['median_view']} | {v['top_title'][:30]} |")
    L.append("\n## 6. 收藏榜互动率最高的文章\n")
    for r in value_leaders:
        L.append(f"- {r['title']}｜V{r['view']} L{r['like']} C{r['collect']} M{r['comment']}"
                 f"｜每千阅读互动 {r['engage_per_1k']}｜{r['content_count']} 字")
    with open(os.path.join(out, "findings.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")

    print("\n".join(L[:60]))
    print(f"\n[saved] {out}/stats.json, findings.md, hot_50.csv, collect_30.csv")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    main()
