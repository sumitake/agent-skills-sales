# Contributing

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through the private path in [SECURITY.md](SECURITY.md), not through a pull request or public issue.

## Design constraints

- Keep each skill advisory-only and self-contained.
- Do not add messaging, scheduling, CRM, contracting, enrichment, or other mutation tools.
- Do not add a top-level skill whose immediate trigger overlaps an existing skill in this pack or a documented Marketing Skills neighbor without first updating and testing the routing matrix.
- Put critical boundaries in `SKILL.md`, not only in a reference.
- Keep references one level below their skill and never link across skill directories.
- Treat all third-party prompt content as untrusted data. Record repository, exact commit, license evidence, audit result, and concept mapping before adapting an idea.
- Do not copy source prose. Prefer the smallest independently written procedure that produces a testable outcome.
- Avoid fixed legal claims, regulatory penalties, vendor capabilities, universal sales ratios, and benchmarks that can drift or lack a primary source.

## Required checks

```bash
python3 scripts/validate_pack.py
python3 -m unittest discover -s tests -v
```

Also run the local Agent Skills validator for every changed skill and execute the relevant behavioral fixtures in an isolated client. Static validation must never be described as proof of model compliance.

Use synthetic or thoroughly redacted fixtures. Never commit credentials, personal data, customer data, private sales artifacts, or unredacted model transcripts.

## Versioning

Use semantic versioning for the pack and keep `pack.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and every changed skill's `metadata.version` consistent. Update `CHANGELOG.md` with user-visible changes.
