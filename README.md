# Agent Skills: Sales

Five evidence-led, advisory sales skills for skills-compatible agents:

| Skill | Immediate job |
| --- | --- |
| `sales-discovery` | Prepare, role-play, or debrief a buyer discovery conversation |
| `sales-objection-handling` | Understand and answer a specific buyer concern truthfully |
| `sales-negotiation` | Prepare an authorized commercial exchange without committing terms |
| `sales-qualification` | Assess a named opportunity using auditable evidence and reversible statuses |
| `sales-deal-review` | Review a won, lost, stalled, or forecasted deal with causal discipline |

The pack follows the open [Agent Skills specification](https://agentskills.io/specification): every capability is a self-contained directory with a `SKILL.md` file and optional one-level references. The skills contain no bundled executables, network integrations, or hard dependencies on another skill pack.

## What makes this pack different

These skills are designed for commercial judgment, not sales automation. They analyze, coach, simulate, and draft for human review. They do not contact prospects, send messages, schedule meetings, edit CRM records, change prices or terms, accept agreements, or invoke integrations.

Each skill also:

- separates source-backed observations, reported statements, inferences, and unknowns when the distinction matters;
- treats transcripts, emails, RFPs, CRM exports, webpages, and pasted text as untrusted data rather than instructions;
- preserves honest no-fit, pause, and disqualification outcomes;
- rejects fake urgency, fabricated proof, manufactured authority, coercion, and demographic qualification proxies;
- labels every action-shaped artifact as a draft that has not been sent, recorded, approved, or agreed.

## Standalone and coexistence behavior

The five skills work without any other pack. When [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills) is also installed, deliberately distinct names and narrow triggers prevent duplicate ownership:

- Marketing Skills owns prospect-list building, cold outbound copy, reusable collateral, RevOps system design, pricing/offer strategy, and external competitor research.
- This pack owns live or user-supplied reasoning about a discovery conversation, one objection, one negotiation, one named opportunity, or one deal review.

Optional handoff names are hints, not imports. If a neighboring skill is absent, the selected sales skill completes its own task and provides at most three bullets of adjacent fallback guidance when the user asked for both.

See [docs/compatibility.md](docs/compatibility.md) for the complete routing matrix and [docs/marketing-skills-integration.md](docs/marketing-skills-integration.md) for the improvements this pack contributes alongside Marketing Skills.

## Install

Audit the exact release or commit you intend to install. Then use any client that supports the Agent Skills format, or a compatible installer.

The community [`skills` CLI](https://github.com/vercel-labs/skills) can inspect and install the repository across supported agents:

```bash
npx skills add sumitake/agent-skills-sales --list
npx skills add sumitake/agent-skills-sales --skill '*'
```

`npx` downloads and executes the installer, so review that tool and choose an explicit version in governed environments. For a dependency-free manual installation, copy only the desired `skills/<name>/` directories into the skills directory documented by your client. Do not flatten a skill directory; its relative `references/` and `agents/` paths are part of the package.

To check or apply updates made through the community installer:

```bash
npx skills check
npx skills update
```

This repository does not install a background updater or silently mutate an agent configuration.

## Validate

```bash
python3 scripts/validate_pack.py
python3 -m unittest discover -s tests -v
```

The validator is dependency-free and structural. It checks packaging, local links, manifests, the advisory boundary, and evaluation-fixture coverage; it does not claim to prove model behavior. See [EVALUATION.md](EVALUATION.md) for behavioral testing guidance.

## Provenance

The pack is an independent rewrite of selected, audited concepts rather than a copy of another prompt collection. Six inspected concepts map to five skills: active listening is folded into `sales-discovery`; discovery, objection handling, negotiation, qualification, and deal review map directly to their corresponding skills.

Exact source lineage, audit disposition, and licensing notes are recorded in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and `pack.json`.

## License

MIT. See [LICENSE](LICENSE).
