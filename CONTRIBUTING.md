# Contributing

## What belongs here

- Improvements to the writing workflow, title formulas, skeletons and anti-patterns in `skills/juejin-hot-article/`.
- Fresh data snapshots and updated statistics (see below).
- New examples, translations, or compatibility fixes for another Agent Skills client.
- Bug fixes in the three Python scripts.

## What does not

- Fabricated data, benchmark numbers, screenshots or citations. The skill explicitly forbids inventing evidence; contributions that do will be rejected.
- Advice about buying views, engagement pods, vote manipulation or title-bait that the body cannot deliver.
- Changes that only tune wording for a single platform's algorithm without evidence.

## Local checks

Before opening a PR, run from the repository root:

```bash
python scripts/validate_skill.py
python skills/juejin-hot-article/scripts/score_article.py examples/draft.md
python -m py_compile skills/juejin-hot-article/scripts/*.py scripts/validate_skill.py
```

`validate_skill.py` uses only the standard library and checks: frontmatter fields and limits, `name` matching the parent directory, every `references/` / `scripts/` / `assets/` path referenced from `SKILL.md`, Python syntax, and CSV row counts. CI runs the same checks on Ubuntu.

## Refreshing the dataset

```bash
python skills/juejin-hot-article/scripts/fetch_juejin.py --out ./snapshot --limit 50
python skills/juejin-hot-article/scripts/analyze_juejin.py --data ./snapshot --out ./snapshot/analysis
```

Then:

1. Replace `skills/juejin-hot-article/references/data/hot_50.csv` and `collect_30.csv` with `snapshot/analysis/*.csv`.
2. Update the numbers in `references/research-report.md`, `references/platform-rules.md` and the root `README.md`.
3. If the fitted coefficients in `snapshot/analysis/stats.json` changed, re-derive the formula and note it in `CHANGELOG.md`.
4. Record the new snapshot date in `SKILL.md` frontmatter (`metadata.data_snapshot`).

Do not commit the raw `snapshot/` directory — `.gitignore` excludes `data/raw/`; keep raw API payloads out of the repository to avoid shipping third-party article bodies.

## Commit style

Use short, imperative commit subjects (`fix: ...`, `docs: ...`, `data: ...`). Keep one logical change per commit.

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
