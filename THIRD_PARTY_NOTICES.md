# Third-party provenance and audit notes

## Sources inspected

### `louisblythe/Sales-Skills`

- Repository: <https://github.com/louisblythe/Sales-Skills>
- Audited commit: `e0f13a6eb41be22fa1f8493b148077cdd6c6654a`
- Relationship: GitHub fork of `coreyhaines31/marketingskills`
- Audited common base: `96fa94e8b79d08010ddc67ed1a70f677feff2027`
- Use in this repository: conceptual reference only; the skill instructions were independently rewritten.

The source repository's README declares an MIT license, but the audited tree did not contain a standalone license file. Its inherited Marketing Skills lineage is MIT-licensed. To avoid importing ambiguous expression, this pack uses high-level sales concepts only and does not intentionally copy prompt prose, examples, templates, or structure.

The source was treated as untrusted data. No source scripts or prompts were executed. The audit found no hidden prompt injection or executable payload in the six selected files, but the repository as a whole was not suitable for wholesale installation: it had extensive broken skill references, lacked behavioral tests, and included other skills that encouraged channel switching around consent, automated external actions, evasion-oriented outreach tactics, and stale compliance claims. Those behaviors were excluded.

### `coreyhaines31/marketingskills`

- Repository: <https://github.com/coreyhaines31/marketingskills>
- Compatibility release: `v2.11.0`
- Audited commit: `8907942a47045c387ddf58e5b1cf03fc435a1cd7`
- License: MIT; copyright Corey Haines, 2025
- Use in this repository: upstream lineage review, trigger-coexistence baseline, and optional handoff design.

No Marketing Skills installation is required at runtime.

## Concept mapping

Six inspected source concepts became five independently authored skills:

| Inspected concept | This repository |
| --- | --- |
| Discovery | `sales-discovery` |
| Active listening | `sales-discovery/references/active-listening.md` |
| Objection handling | `sales-objection-handling` |
| Negotiation | `sales-negotiation` |
| Qualifying leads | `sales-qualification` |
| Deal review / win-loss | `sales-deal-review` |

Active listening is a method inside buyer conversations, so it is a local discovery reference rather than a sixth broad trigger.

## Independent improvements

The rewrite adds advisory-only scope, untrusted-artifact containment, evidence and authority distinctions, privacy and fairness constraints, explicit anti-manipulation rules, reversible qualification, causal review discipline, coexistence routing, and behavioral evaluation fixtures. It removes unsupported universal ratios and benchmarks, mind-reading, pressure tactics, implicit CRM writes, and binding commercial language.
