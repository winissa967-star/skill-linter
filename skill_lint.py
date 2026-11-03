#!/usr/bin/env python3
"""skill_lint.py - lint an Agent Skills folder (the folder that holds SKILL.md).

Usage:
    python3 skill_lint.py PATH_TO_SKILL_FOLDER [--strict] [--fix] [--json]

Exit codes: 0 = no errors, 1 = errors (or warnings with --strict), 2 = bad usage.
Standard library only. Read-only by default; use --fix to apply safe corrections.
"""
import json
import re
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KNOWN_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
MAX_BODY_TOKENS = 5000

RISKY = [
    (r"\brm\s+-[a-zA-Z]*[rR]", "recursive delete (rm -r)"),
    (r"curl[^|\n]*\|\s*(sudo\s+)?(ba|z)?sh\b", "pipes a download into a shell"),
    (r"\bsudo\b", "sudo"),
    (r"chmod\s+(-R\s+)?777", "chmod 777"),
    (r"git\s+push\s+(.*\s)?(--force|-f)\b", "git force push"),
    (r"\bDROP\s+(TABLE|DATABASE)\b", "SQL DROP"),
    (r"\beval\s*\(", "eval()"),
]


def split_frontmatter(text):
    """Split YAML frontmatter from body. Returns (fm_dict, body_text, raw_fm_lines)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text, None
    
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            raw_fm = lines[1:i]
            body = "\n".join(lines[i + 1:])
            if HAS_YAML:
                try:
                    fm = yaml.safe_load("\n".join(raw_fm)) or {}
                    if not isinstance(fm, dict):
                        return None, text, None
                    return fm, body, raw_fm
                except yaml.YAMLError:
                    return None, text, None
            else:
                return parse_simple_yaml(raw_fm), body, raw_fm
    return None, text, None


def parse_simple_yaml(lines):
    """Fallback parser for simple key-value pairs."""
    fields = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" in line and not line[0] in " \t":
            key, _, val = line.partition(":")
            fields[key.strip()] = val.strip().strip('"\'')
    return fields


def lint(skill_dir, fix=False):
    out = []
    fixes = []

    def add(level, msg):
        out.append((level, msg))

    names = {p.name for p in skill_dir.iterdir()}
    if "SKILL.md" not in names:
        wrong = next((n for n in names if n.lower() == "skill.md"), None)
        if wrong and fix:
            (skill_dir / wrong).rename(skill_dir / "SKILL.md")
            fixes.append(f"Renamed '{wrong}' to 'SKILL.md'")
            names.remove(wrong)
            names.add("SKILL.md")
        else:
            hint = f" (found '{wrong}')" if wrong else ""
            add("ERROR", f"SKILL.md not found{hint}")
            return out, fixes

    skill_path = skill_dir / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8", errors="replace").lstrip("\ufeff")
    fm, body, raw_fm = split_frontmatter(text)
    
    if fm is None:
        add("ERROR", "SKILL.md: invalid frontmatter (must be valid YAML between '---' markers)")
        return out, fixes

    name = str(fm.get("name", ""))
    if not name:
        add("ERROR", "name: missing or empty")
    else:
        if len(name) > 64:
            add("ERROR", f"name: {len(name)} chars, max 64")
        if not NAME_RE.match(name):
            add("ERROR", "name: use lowercase, digits, hyphens only")
        if name != skill_dir.name:
            add("ERROR", f"name: '{name}' must match folder name '{skill_dir.name}'")

    desc = str(fm.get("description", ""))
    if not desc:
        add("ERROR", "description: missing or empty")
    else:
        if len(desc) > 1024:
            add("ERROR", f"description: {len(desc)} chars, max 1024")
        if len(desc) < 30:
            add("WARN", "description: too short (<30 chars)")
        if not re.search(r"\b(use|when|whenever|if|trigger)", desc, re.I):
            add("WARN", "description: missing 'when to use' guidance")

    if "compatibility" in fm:
        c = str(fm["compatibility"])
        if not c or len(c) > 500:
            add("ERROR", "compatibility: must be 1-500 chars")

    for k in fm:
        if k not in KNOWN_FIELDS:
            add("INFO", f"field '{k}' not in spec")

    if not body.strip():
        add("WARN", "body: no instructions after frontmatter")
    elif len(body) / 4 > MAX_BODY_TOKENS:
        add("WARN", f"body: ~{len(body)//4} tokens (max {MAX_BODY_TOKENS})")

    root = skill_dir.resolve()
    for target in re.findall(r"\[[^\]]*\]\(([^)\s]+)\)", body):
        if "://" in target or target.startswith(("#", "mailto:")):
            continue
        path = (root / target.split("#")[0]).resolve()
        if root not in path.parents and path != root:
            add("WARN", f"link '{target}' points outside skill folder")
        elif not path.exists():
            add("ERROR", f"broken link: '{target}'")

    files = [(skill_dir / "SKILL.md", "SKILL.md")]
    scripts = skill_dir / "scripts"
    if scripts.is_dir():
        files += [(p, str(p.relative_to(skill_dir))) for p in sorted(scripts.rglob("*"))
                  if p.is_file() and not p.is_symlink() and p.stat().st_size < 1_000_000]
    
    for path, label in files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(lines, 1):
            for pattern, what in RISKY:
                if re.search(pattern, line):
                    add("WARN", f"{label}:{n}: {what}")

    return out, fixes


def main(argv):
    flags = [a for a in argv[1:] if a.startswith("--")]
    args = [a for a in argv[1:] if not a.startswith("--")]
    
    if len(args) != 1 or any(f not in ("--strict", "--fix", "--json") for f in flags):
        print(__doc__)
        return 2
    
    skill_dir = Path(args[0])
    if not skill_dir.is_dir():
        print(f"error: not a folder: {skill_dir}")
        return 2
    
    findings, fixes = lint(skill_dir.resolve(), fix="--fix" in flags)
    
    if "--json" in flags:
        output = {
            "errors": sum(1 for l, _ in findings if l == "ERROR"),
            "warnings": sum(1 for l, _ in findings if l == "WARN"),
            "findings": [{"level": l, "msg": m} for l, m in findings],
            "fixes_applied": fixes
        }
        print(json.dumps(output, indent=2))
    else:
        for level, msg in findings:
            print(f"{level:<5} {msg}")
        if fixes:
            print("\nFIXES APPLIED:")
            for f in fixes:
                print(f"  ✓ {f}")
        errors = sum(1 for l, _ in findings if l == "ERROR")
        warns = sum(1 for l, _ in findings if l == "WARN")
        print(f"\n{errors} error(s), {warns} warning(s)")
    
    errors = sum(1 for l, _ in findings if l == "ERROR")
    warns = sum(1 for l, _ in findings if l == "WARN")
    return 1 if errors or (warns and "--strict" in flags) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
