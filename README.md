# skill-linter
## 🚀 Available Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [content-writer](skills/content-writer/) | SEO-optimized content writer | ✅ Tested |
| [data-analyzer](skills/data-analyzer/) | Data analysis & insights | ✅ Tested |
| [social-media-pro](skills/social-media-pro/) | Social media automation | ✅ Tested |

## 🔧 Quality Assurance
All skills are validated using our automated [skill linter](skill_lint.py).


Smart linter for AI Agent Skills folders
✅ Validates SKILL.md frontmatter (YAML)
✅ Checks name/description compliance with the spec
🔒 Detects risky commands (rm -rf, sudo, curl|sh, etc.)
🔗 Validates local links and file references
🤖 Auto-fix mode (--fix) for common issues
📊 JSON output for CI/CD integration (--json)
Features
python3 skill_lint.py PATH_TO_SKILL_FOLDER [--strict] [--fix] [--json]
Usage
skill