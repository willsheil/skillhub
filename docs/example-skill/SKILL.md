---
name: example-skill
description: An example skill demonstrating the SKILL.md format for Agent Skills. Use this as a reference when creating new skills.
license: Apache-2.0
metadata:
  author: example-org
  version: "1.0"
---

# Example Skill

This is an example skill that demonstrates the SKILL.md format for the Agent Skills specification.

## When to Use

Use this skill as a reference when:
- Creating new skills for the registry
- Understanding the SKILL.md format
- Testing the skill registry functionality

## Instructions

1. Create a directory named after your skill (matching the `name` field)
2. Add a `SKILL.md` file with YAML frontmatter
3. Include optional directories like `scripts/`, `references/`, or `assets/` as needed
4. Package as a ZIP file: `{skill-name}-{version}.zip`

## File Structure

```
example-skill/
├── SKILL.md          # Required: skill definition and instructions
├── scripts/          # Optional: executable code
│   └── example.py
├── references/       # Optional: additional documentation
│   └── REFERENCE.md
└── assets/           # Optional: templates and resources
    └── template.txt
```

## YAML Frontmatter

Required fields:
- `name`: Skill identifier (max 64 chars, lowercase letters/numbers/hyphens)
- `description`: What the skill does and when to use it (max 1024 chars)

Optional fields:
- `license`: License name or reference
- `compatibility`: Environment requirements (max 500 chars)
- `metadata`: Key-value mapping for additional data (author, version, etc.)
- `allowed-tools`: Space-delimited list of pre-approved tools

## Examples

### Good Description

```yaml
description: Extracts text and tables from PDF files, fills PDF forms, and merges multiple PDFs. Use when working with PDF documents or when the user mentions PDFs, forms, or document extraction.
```

### Poor Description

```yaml
description: Helps with PDFs.
```

## References

- [Agent Skills Specification](https://agentskills.io/specification)
