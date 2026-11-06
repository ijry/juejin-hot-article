# Changelog

All notable changes to this project are documented here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-11-06

### Added
- Standard [Agent Skills](https://agentskills.io/specification) skill `juejin-hot-article`, installable in Codex, Claude Code, WorkBuddy and other compatible clients.
- Research dataset: 50 articles from the Juejin 3-day article board, 30 from the 3-month collect board, plus 7 category boards (20 items each). Per-article features are shipped as CSV.
- Reversed-engineered heat model: `hot_index ≈ 9 × round(views/20 + likes + comments)`; 1 like/comment ≈ 20 views; collects do not affect the article board.
- `references/`: research report, 10 title formulas with real cases, 5 article skeletons, platform rules, publishing SOP and anti-patterns.
- `scripts/score_article.py`: 100-point pre-publish scorer (title/topic/structure/trust/engagement/publish config) with hard-rule checks.
- `scripts/fetch_juejin.py` + `scripts/analyze_juejin.py`: refresh the data and recompute all statistics with the Python standard library only.
- `install.sh`: one-command installation into Codex / Claude Code / WorkBuddy / project scopes, including the WorkBuddy metadata shim.
- `scripts/validate_skill.py` and a GitHub Actions workflow that validates frontmatter, file references, script syntax and CSV integrity on every push.
- `examples/`: a real-data demo draft, prompt cookbook and cover asset.

### Verified
- `npx skills add ijry/juejin-hot-article --list -y` discovers 1 skill; `-a codex -y --copy` installs it to `.agents/skills/juejin-hot-article/`.
- `install.sh` installs to all three client targets; Codex / Claude Code copies stay spec-clean while the WorkBuddy copy receives the `agent_created` shim.
- `python scripts/validate_skill.py`: 41 checks passed, 0 errors. `examples/draft.md` scores 98/100. GitHub Actions `validate` workflow passes on push.

### Notes
- All numbers are a single snapshot taken at 2026-11-06 08:55 (UTC+8). Platform algorithms may change; rerun the fetch/analyze chain to refresh.
- The heat formula is an empirical fit, not an official platform disclosure.
