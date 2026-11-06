#!/usr/bin/env bash
# Install the juejin-hot-article Agent Skill into compatible clients.
#
# Usage:
#   ./install.sh --scope global  --agent codex
#   ./install.sh --scope project --agent claude-code
#   ./install.sh --scope global  --agent all --force
#   ./install.sh --scope project --agent codex --dry-run
#
# Client target directories follow the Agent Skills ecosystem convention:
#   codex / cline / warp / zed ...  .agents/skills/      ~/.agents/skills/
#   claude-code                     .claude/skills/      ~/.claude/skills/
#   workbuddy                       .workbuddy-ai/skills ~/.workbuddy-ai/skills/
#
# POSIX-friendly, no dependencies beyond bash, cp, mkdir and awk.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="juejin-hot-article"

SCOPE="global"
AGENTS="codex"
DRY_RUN=0
FORCE=0
WORKBUDDY_SHIM=1

usage() {
  cat <<'EOF'
Usage: install.sh [options]

  --scope <project|global>   Install into the current project (default: global)
  --agent <name|all>         codex, claude-code, workbuddy, or comma-separated
                             list / "all" (default: codex)
  --skill <name>             Skill directory name (default: juejin-hot-article)
  --force                    Replace an existing installation (backs it up first)
  --no-shim                  Do not add WorkBuddy's agent_created metadata
  --dry-run                  Print planned actions without changing anything
  -h, --help                 Show this help

Examples:
  ./install.sh --scope global --agent codex
  ./install.sh --scope project --agent claude-code --force
  ./install.sh --scope global --agent all --dry-run
  curl -fsSL .../install.sh | bash -s -- --scope global --agent codex
EOF
}

die() { printf 'error: %s\n' "$*" >&2; exit 2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)        [[ $# -ge 2 ]] || die "--scope needs a value"; SCOPE="$2"; shift 2 ;;
    --scope=*)      SCOPE="${1#*=}"; shift ;;
    --agent)        [[ $# -ge 2 ]] || die "--agent needs a value"; AGENTS="$2"; shift 2 ;;
    --agent=*)      AGENTS="${1#*=}"; shift ;;
    --skill)        [[ $# -ge 2 ]] || die "--skill needs a value"; SKILL_NAME="$2"; shift 2 ;;
    --skill=*)      SKILL_NAME="${1#*=}"; shift ;;
    --force|-f)     FORCE=1; shift ;;
    --no-shim)      WORKBUDDY_SHIM=0; shift ;;
    --dry-run)      DRY_RUN=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              die "unknown option: $1 (try --help)" ;;
  esac
done

case "$SCOPE" in
  project|global) ;;
  *) die "--scope must be 'project' or 'global'" ;;
esac

SRC="$SCRIPT_DIR/skills/$SKILL_NAME"
[[ -f "$SRC/SKILL.md" ]] || die "skill not found at $SRC (run this from a cloned repository)"

if [[ "$AGENTS" == "all" ]]; then
  AGENT_LIST=(codex claude-code workbuddy)
else
  IFS=',' read -r -a AGENT_LIST <<< "$AGENTS"
fi

for agent in "${AGENT_LIST[@]}"; do
  case "$agent" in
    codex|claude-code|workbuddy) ;;
    *) die "unknown agent: $agent (use codex, claude-code, workbuddy or all)" ;;
  esac
done

if [[ "$SCOPE" == "project" ]]; then
  BASE="$PWD"
else
  BASE="${HOME:-$(cd ~ && pwd)}"
fi

dest_for() {
  local agent="$1"
  case "$agent" in
    codex)        printf '%s/.agents/skills/%s'        "$BASE" "$SKILL_NAME" ;;
    claude-code)  printf '%s/.claude/skills/%s'        "$BASE" "$SKILL_NAME" ;;
    workbuddy)    printf '%s/.workbuddy-ai/skills/%s'  "$BASE" "$SKILL_NAME" ;;
  esac
}

apply_workbuddy_shim() {
  # WorkBuddy marks AI-authored skills with `agent_created: true`. The published
  # copy stays spec-clean; only the local WorkBuddy install gets this field.
  local md="$1/SKILL.md"
  [[ -f "$md" ]] || return 0
  grep -q '^agent_created:' "$md" && return 0
  awk '
    BEGIN { inserted = 0; fences = 0 }
    /^---[[:space:]]*$/ {
      fences++
      if (fences == 2 && !inserted) { print "agent_created: true"; inserted = 1 }
    }
    { print }
  ' "$md" > "$md.tmp" && mv "$md.tmp" "$md"
  printf '         added WorkBuddy metadata (agent_created: true)\n'
}

printf 'Skill   : %s\n' "$SKILL_NAME"
printf 'Source  : %s\n' "$SRC"
printf 'Scope   : %s (base: %s)\n' "$SCOPE" "$BASE"
printf 'Agents  : %s\n' "${AGENT_LIST[*]}"
[[ $DRY_RUN -eq 1 ]] && printf 'Mode    : DRY RUN (no files will be changed)\n'
printf '\n'

status=0
for agent in "${AGENT_LIST[@]}"; do
  dest="$(dest_for "$agent")"
  printf '  [%s]\n' "$agent"

  if [[ -e "$dest" ]]; then
    if [[ $FORCE -eq 0 ]]; then
      printf '    skip: already exists -> %s\n' "$dest"
      printf '          use --force to replace (the old copy is backed up)\n'
      status=1
      continue
    fi
    backup="${dest}.bak.$(date +%Y%m%d%H%M%S)"
    if [[ $DRY_RUN -eq 1 ]]; then
      printf '    would back up %s -> %s\n' "$dest" "$backup"
    else
      mv "$dest" "$backup"
      printf '    backed up existing install -> %s\n' "$backup"
    fi
  fi

  if [[ $DRY_RUN -eq 1 ]]; then
    printf '    would install -> %s\n' "$dest"
  else
    mkdir -p "$(dirname "$dest")"
    cp -R "$SRC" "$dest"
    printf '    installed -> %s\n' "$dest"
    if [[ "$agent" == "workbuddy" && $WORKBUDDY_SHIM -eq 1 ]]; then
      apply_workbuddy_shim "$dest"
    fi
  fi
done

printf '\n'
if [[ $DRY_RUN -eq 1 ]]; then
  printf 'Dry run complete. Re-run without --dry-run to install.\n'
else
  printf 'Verify with:\n'
  printf '  test -f "%s" && echo OK\n' "$(dest_for "${AGENT_LIST[0]}")/SKILL.md"
  printf '  python "%s/scripts/score_article.py" examples/draft.md\n' "$(dest_for "${AGENT_LIST[0]}")"
  printf '\nIn Codex or Claude Code, ask: "use juejin-hot-article, give me 8 title candidates for <topic>".\n'
fi

exit "$status"
