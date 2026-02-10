---
name: auditing-python-security
description: Audits Python code for security vulnerabilities using Bandit, pip-audit, Safety, and detect-secrets. Identifies SQL injection, command injection, hardcoded credentials, weak cryptography, and insecure deserialization. Use when reviewing Python library security, setting up security scanning in CI, auditing Python applications, or implementing secure coding patterns.
metadata:
    version: "1.0.5"
    author: "w00545471"  # 替换为你的工号
---

# Python Security Auditing

Comprehensive security auditing for Python codebases using industry-standard tools.

## When to Use

- Auditing Python libraries or applications for security vulnerabilities
- Setting up security scanning in CI/CD pipelines
- Reviewing code for common Python security anti-patterns
- Implementing secure coding patterns in Python
- Pre-deployment security checks
- Dependency vulnerability assessment

## When NOT to Use

- Non-Python codebases (use language-specific security skills instead)
- Cryptographic implementation review (use `constant-time-analysis` for crypto code)
- Smart contract auditing (use `building-secure-contracts`)
- General code quality review without security focus

## Quick Start

```bash
# Static analysis
bandit -r src/ -ll                    # High severity only
pip-audit                             # Dependency vulnerabilities
detect-secrets scan > .secrets.baseline  # Secrets detection
```

Or use the comprehensive scanner:

```bash
uv run {baseDir}/scripts/security_scan.py /path/to/project
```

## Tool Configuration

**Bandit (.bandit):**
```yaml
exclude_dirs: [tests/, docs/, .venv/]
skips: [B101]  # assert_used - OK in tests
```

**pip-audit:**
```bash
pip-audit -r requirements.txt         # Scan requirements
pip-audit --fix                       # Auto-fix vulnerabilities
```

## Common Vulnerabilities

| Issue | Bandit ID | Fix |
|-------|-----------|-----|
| SQL injection | B608 | Use parameterized queries |
| Command injection | B602 | subprocess without shell=True |
| Hardcoded secrets | B105, B106 | Environment variables |
| Weak crypto | B303 | Use SHA-256+, bcrypt for passwords |
| Pickle untrusted data | B301 | Use JSON instead |
| Path traversal | B108 | Validate with Path.resolve() |

## Secure Patterns

```python
# SQL - Parameterized query
conn.execute("SELECT * FROM users WHERE id = ?", (user_id,))

# Commands - No shell
subprocess.run(["cat", filename], check=True)

# Secrets - Environment
API_KEY = os.environ.get("API_KEY")

# Paths - Validate
base = Path("/data").resolve()
file_path = (base / filename).resolve()
if not file_path.is_relative_to(base):
    raise ValueError("Invalid path")
```

For detailed vulnerability patterns and secure alternatives, see [resources/VULNERABILITY_PATTERNS.md](resources/VULNERABILITY_PATTERNS.md).

## CI Integration

```yaml
# .github/workflows/security.yml
- run: bandit -r src/ -ll
- run: pip-audit
- run: detect-secrets scan --all-files
```

## Audit Checklist

```
Code:
- [ ] No SQL injection (parameterized queries)
- [ ] No command injection (no shell=True)
- [ ] No hardcoded secrets
- [ ] No weak crypto (MD5/SHA1)
- [ ] Input validation on external data
- [ ] Path traversal prevention

Dependencies:
- [ ] pip-audit clean
- [ ] Minimal dependencies
- [ ] From trusted sources

CI:
- [ ] Security scan on every PR
- [ ] Weekly dependency scan
```
