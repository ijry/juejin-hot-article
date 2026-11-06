#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validate this repository as a standard Agent Skills distribution.

Standard library only. Run from anywhere; all paths resolve against the
repository root (the parent directory of this script's folder).

    python scripts/validate_skill.py
    python scripts/validate_skill.py --json

Exit code is 0 when there are no errors, 1 otherwise. Warnings never fail the
build. The same script runs in GitHub Actions on every push.

Checks
------
  1. SKILL.md exists and has a well-formed frontmatter block.
  2. Required fields (name, description) and spec-allowed optional fields only.
  3. name matches its parent directory and the ^[a-z0-9]+(-[a-z0-9]+)*$ rule.
  4. description is non-empty and within the 1024 character limit.
  5. Every references/ scripts/ assets/ path mentioned in SKILL.md exists.
  6. Every Python file shipped with the skill compiles.
  7. CSV snapshots have headers, expected row counts and required columns.
  8. LICENSE exists and agrees with the SKILL.md `license` field.
  9. Required repository files are present (README, installer, CI, examples).
 10. No client-proprietary top-level frontmatter field leaks into the
     distributable copy (e.g. WorkBuddy's `agent_created`).
"""

import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_NAME = "juejin-hot-article"
SKILL_DIR = os.path.join(ROOT, "skills", SKILL_NAME)
SKILL_MD = os.path.join(SKILL_DIR, "SKILL.md")

# https://agentskills.io/specification -- top-level frontmatter fields.
REQUIRED_FIELDS = {"name", "description"}
ALLOWED_FIELDS = {
    "name", "description", "license", "compatibility", "metadata", "allowed-tools",
}
PROPRIETARY_FIELDS = {"agent_created"}

EXPECTED_CSV = {
    "hot_50.csv": 50,
    "collect_30.csv": 30,
}
REQUIRED_CSV_COLUMNS = {
    "rank", "title", "view", "like", "collect", "comment", "hot_rank",
    "content_count", "title_len", "tag_count",
}

REQUIRED_REPO_FILES = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "install.sh",
    "scripts/validate_skill.py",
    ".github/workflows/validate.yml",
    "examples/draft.md",
    "examples/prompts.md",
    "skills/juejin-hot-article/agents/openai.yaml",
    "skills/juejin-hot-article/assets/article_skeleton.md",
]

checks = []


def record(status, message):
    checks.append({"status": status, "message": message})


def passed(message):
    record("PASS", message)


def failed(message):
    record("FAIL", message)


def warned(message):
    record("WARN", message)


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def parse_frontmatter(text):
    """Return (top_level_fields, body). Nested metadata lines are skipped."""
    match = re.match(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", text, re.S)
    if not match:
        return None, text
    fields = {}
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line[:1].isspace():
            continue  # nested key, e.g. metadata.author
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip().strip('"\'')
    return fields, text[match.end():]


def check_frontmatter():
    if not os.path.isfile(SKILL_MD):
        failed("SKILL.md not found at %s" % SKILL_MD)
        return None, ""
    text = read_text(SKILL_MD)
    passed("SKILL.md exists (%d bytes)" % len(text.encode("utf-8")))

    fields, body = parse_frontmatter(text)
    if fields is None:
        failed("SKILL.md has no valid `---` frontmatter block")
        return None, body

    for key in sorted(REQUIRED_FIELDS):
        if fields.get(key):
            passed("required frontmatter field present: %s" % key)
        else:
            failed("missing or empty required frontmatter field: %s" % key)

    unknown = set(fields) - ALLOWED_FIELDS
    if unknown:
        failed("non-standard top-level frontmatter field(s): %s" % ", ".join(sorted(unknown)))
    else:
        passed("all top-level frontmatter fields are spec-allowed")

    leaked = PROPRIETARY_FIELDS & set(fields)
    if leaked:
        failed("client-proprietary field leaked into distributable copy: %s"
               % ", ".join(sorted(leaked)))
    else:
        passed("no client-proprietary frontmatter field in distributable copy")

    name = fields.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        failed("name %r violates ^[a-z0-9]+(-[a-z0-9]+)*$" % name)
    elif len(name) > 64:
        failed("name exceeds 64 characters")
    elif name != os.path.basename(SKILL_DIR):
        failed("name %r does not match parent directory %r"
               % (name, os.path.basename(SKILL_DIR)))
    else:
        passed("name %r matches parent directory and spec format" % name)

    description = fields.get("description", "")
    if len(description) > 1024:
        failed("description is %d chars (limit 1024)" % len(description))
    elif description:
        passed("description present (%d chars, <= 1024)" % len(description))

    if fields.get("license") == "MIT":
        passed("license field declares MIT")
    else:
        failed("license field should be MIT, got %r" % fields.get("license"))

    if not re.search(r"^#\s+\S", body, re.M):
        warned("SKILL.md body has no H1 heading")
    else:
        passed("SKILL.md body has an H1 heading")

    return fields, body


def check_referenced_paths(body):
    refs = set(re.findall(r"`((?:references|scripts|assets)/[^`\s]+)`", body))
    if not refs:
        failed("SKILL.md references no resources at all")
        return
    for rel in sorted(refs):
        path = os.path.join(SKILL_DIR, *rel.split("/"))
        if os.path.isfile(path):
            passed("referenced resource exists: %s" % rel)
        else:
            failed("SKILL.md references a missing file: %s" % rel)


def check_python_syntax():
    found = 0
    for base, dirs, files in os.walk(SKILL_DIR):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for filename in files:
            if not filename.endswith(".py"):
                continue
            found += 1
            path = os.path.join(base, filename)
            rel = os.path.relpath(path, ROOT).replace("\\", "/")
            try:
                compile(read_text(path), path, "exec")
                passed("compiles: %s" % rel)
            except SyntaxError as exc:
                failed("syntax error in %s: %s" % (rel, exc))
    if found == 0:
        failed("no Python scripts found under the skill directory")


def check_csv_snapshots():
    for filename, expected in sorted(EXPECTED_CSV.items()):
        path = os.path.join(SKILL_DIR, "references", "data", filename)
        if not os.path.isfile(path):
            failed("missing CSV snapshot: references/data/%s" % filename)
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        if not rows:
            failed("empty CSV: %s" % filename)
            continue
        header, data = set(rows[0]), [r for r in rows[1:] if any(c.strip() for c in r)]
        missing = REQUIRED_CSV_COLUMNS - header
        if missing:
            failed("%s missing columns: %s" % (filename, ", ".join(sorted(missing))))
        else:
            passed("%s has all %d required columns" % (filename, len(REQUIRED_CSV_COLUMNS)))
        if len(data) == expected:
            passed("%s has %d data rows" % (filename, expected))
        else:
            failed("%s has %d data rows, expected %d" % (filename, len(data), expected))


def check_repository_files():
    for rel in REQUIRED_REPO_FILES:
        path = os.path.join(ROOT, *rel.split("/"))
        if os.path.isfile(path):
            passed("repository file present: %s" % rel)
        else:
            failed("missing repository file: %s" % rel)

    license_path = os.path.join(ROOT, "LICENSE")
    if os.path.isfile(license_path):
        head = read_text(license_path)[:600]
        if "MIT License" in head:
            passed("LICENSE is MIT")
        else:
            failed("LICENSE does not look like MIT")


def check_openai_yaml():
    path = os.path.join(SKILL_DIR, "agents", "openai.yaml")
    if not os.path.isfile(path):
        return
    text = read_text(path)
    for key in ("display_name", "short_description", "default_prompt"):
        if re.search(r"^\s*%s\s*:" % key, text, re.M):
            passed("agents/openai.yaml defines %s" % key)
        else:
            warned("agents/openai.yaml is missing optional key %s" % key)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    _, body = check_frontmatter()
    check_referenced_paths(body)
    check_python_syntax()
    check_csv_snapshots()
    check_repository_files()
    check_openai_yaml()

    errors = [c for c in checks if c["status"] == "FAIL"]
    warnings = [c for c in checks if c["status"] == "WARN"]
    passes = [c for c in checks if c["status"] == "PASS"]
    summary = {"passed": len(passes), "warnings": len(warnings),
               "errors": len(errors), "checks": checks}

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        for item in checks:
            print("%-4s  %s" % (item["status"], item["message"]))
        print("-" * 72)
        print("Summary: %d passed, %d warnings, %d errors"
              % (len(passes), len(warnings), len(errors)))

    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
