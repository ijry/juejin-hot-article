#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch Juejin (juejin.cn) hot-article rankings and article details.

Usage:
    python fetch_juejin.py --out ./data
    python fetch_juejin.py --out ./data --rank-only

Outputs (all UTF-8 JSON):
    rank_hot.json          /hot/articles            (last 3 days, engagement-weighted heat)
    rank_collect.json      /hot/collected-articles (last 3 months, collect-weighted)
    rank_category_<id>.json  per-category article boards (last 7 days)
    details/<article_id>.json  raw article detail payloads
    articles.json          merged, analysis-ready records for the 50 hot articles

API notes (verified 2026-11):
    GET  https://api.juejin.cn/content_api/v1/content/article_rank?category_id=1&type=hot
         type=hot | collect ; category_id=1 means "all categories"
    POST https://api.juejin.cn/content_api/v1/article/detail
         body MUST contain article_id + aid=2608 + client_type=2608 (numbers),
         otherwise the API returns err_no=2 "参数错误".

Only the Python standard library is used. No subprocesses are spawned.
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone

API = "https://api.juejin.cn/content_api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Referer": "https://juejin.cn/hot/articles",
    "Origin": "https://juejin.cn",
}
CATEGORIES = {
    "1": "综合",
    "6809637769959178254": "后端",
    "6809637767543259144": "前端",
    "6809635626879549454": "客户端",
    "6809637773935378440": "人工智能",
    "6809637771511070734": "开发工具",
    "6809637776263217160": "代码人生",
    "6809637772874219534": "阅读",
}
CST = timezone(timedelta(hours=8))


def request_json(url, body=None, retries=3):
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=HEADERS)
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - network resilience
            last = exc
            time.sleep(1.0 + attempt * 1.5)
    raise RuntimeError(f"request failed: {url} :: {last}")


def fetch_rank(rank_type="hot", category_id="1"):
    url = f"{API}/content/article_rank?category_id={category_id}&type={rank_type}"
    result = request_json(url)
    if result.get("err_no") != 0:
        raise RuntimeError(f"rank api error: {result}")
    return result.get("data") or []


def fetch_detail(article_id):
    result = request_json(
        f"{API}/article/detail",
        {"article_id": str(article_id), "aid": 2608, "client_type": 2608},
    )
    if result.get("err_no") != 0 or not result.get("data"):
        raise RuntimeError(f"detail api error for {article_id}: {result}")
    return result["data"]


def save(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def ts_to_iso(value):
    try:
        return datetime.fromtimestamp(int(value), CST).isoformat()
    except (TypeError, ValueError):
        return ""


def build_record(rank, item, detail):
    counter = item.get("content_counter") or {}
    content = item.get("content") or {}
    author = item.get("author") or {}
    info = (detail or {}).get("article_info") or {}
    tags = [t.get("tag_name") for t in (detail or {}).get("tags") or [] if t.get("tag_name")]
    category = ((detail or {}).get("category") or {}).get("category_name", "")
    author_info = (detail or {}).get("author_user_info") or {}
    markdown = info.get("mark_content") or ""
    ctime = info.get("ctime") or content.get("ctime") or 0
    published = ts_to_iso(ctime)
    return {
        "rank": rank,
        "article_id": str(content.get("content_id") or info.get("article_id") or ""),
        "url": f"https://juejin.cn/post/{content.get('content_id') or info.get('article_id') or ''}",
        "title": info.get("title") or content.get("title") or "",
        "brief": (info.get("brief_content") or content.get("brief") or "")[:300],
        "author": author_info.get("user_name") or author.get("name") or "",
        "author_id": str(author.get("user_id") or ""),
        "author_level": (item.get("author_counter") or {}).get("level"),
        "author_follower": (author_info.get("follower_count")
                            or (item.get("author_counter") or {}).get("follower")),
        "author_company": author_info.get("company") or "",
        "author_job": author_info.get("job_title") or "",
        "category": category,
        "category_id": str(content.get("category_id") or info.get("category_id") or ""),
        "tags": tags,
        "tag_count": len(tags),
        "published_at": published,
        "age_hours_at_fetch": round((datetime.now(CST).timestamp() - int(ctime)) / 3600, 1)
        if str(ctime).isdigit() and int(ctime) > 0 else None,
        "view": counter.get("view", info.get("view_count")),
        "like": counter.get("like", info.get("digg_count")),
        "collect": counter.get("collect", info.get("collect_count")),
        "comment": counter.get("comment_count", info.get("comment_count")),
        "hot_rank": counter.get("hot_rank", info.get("hot_index")),
        "is_original": info.get("is_original"),
        "is_english": info.get("is_english"),
        "has_cover": bool(info.get("cover_image")),
        "read_time": info.get("read_time") or "",
        "content_count": info.get("content_count") or 0,
        "catalog_count": len(info.get("catalog") or []),
        "markdown": markdown,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./data", help="output directory")
    parser.add_argument("--limit", type=int, default=50, help="number of hot articles")
    parser.add_argument("--rank-only", action="store_true", help="skip article details")
    args = parser.parse_args()

    out = os.path.abspath(args.out)
    details_dir = os.path.join(out, "details")
    os.makedirs(details_dir, exist_ok=True)

    print("[1/4] fetching hot article board ...", flush=True)
    hot = fetch_rank("hot", "1")[:args.limit]
    save(os.path.join(out, "rank_hot.json"), hot)
    print(f"      {len(hot)} articles", flush=True)

    print("[2/4] fetching comparison boards ...", flush=True)
    collect = fetch_rank("collect", "1")[:args.limit]
    save(os.path.join(out, "rank_collect.json"), collect)
    boards = {}
    for cid, name in CATEGORIES.items():
        if cid == "1":
            continue
        try:
            rows = fetch_rank("hot", cid)[:args.limit]
            boards[name] = rows
            save(os.path.join(out, f"rank_category_{cid}.json"), rows)
            print(f"      {name}: {len(rows)}", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"      {name}: failed ({exc})", flush=True)
        time.sleep(0.2)

    if args.rank_only:
        print("rank-only mode: done.")
        return

    print("[3/4] fetching article details ...", flush=True)
    records = []
    for idx, item in enumerate(hot, 1):
        aid = item["content"]["content_id"]
        cache = os.path.join(details_dir, f"{aid}.json")
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as f:
                detail = json.load(f)
        else:
            try:
                detail = fetch_detail(aid)
                save(cache, detail)
            except Exception as exc:  # noqa: BLE001
                print(f"      #{idx} {aid} failed: {exc}", flush=True)
                detail = {}
            time.sleep(0.25)
        records.append(build_record(idx, item, detail))
        if idx % 10 == 0:
            print(f"      {idx}/{len(hot)}", flush=True)

    print("[4/4] fetching comparison-dataset details + writing merged datasets ...", flush=True)
    collect_records = []
    for idx, item in enumerate(collect, 1):
        aid = item["content"]["content_id"]
        cache = os.path.join(details_dir, f"{aid}.json")
        if os.path.exists(cache):
            with open(cache, encoding="utf-8") as f:
                detail = json.load(f)
        else:
            try:
                detail = fetch_detail(aid)
                save(cache, detail)
            except Exception as exc:  # noqa: BLE001
                print(f"      collect #{idx} {aid} failed: {exc}", flush=True)
                detail = {}
            time.sleep(0.25)
        collect_records.append(build_record(idx, item, detail))

    save(os.path.join(out, "articles.json"), records)
    save(os.path.join(out, "articles_collect.json"), collect_records)
    summary = {
        "fetched_at": datetime.now(CST).isoformat(),
        "hot_count": len(records),
        "collect_board_count": len(collect_records),
        "category_boards": {k: len(v) for k, v in boards.items()},
        "top10": [{"rank": r["rank"], "title": r["title"], "view": r["view"],
                   "hot_rank": r["hot_rank"]} for r in records[:10]],
    }
    save(os.path.join(out, "fetch_summary.json"), summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
