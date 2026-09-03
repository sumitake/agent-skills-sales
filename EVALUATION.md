# Evaluation guide

## What CI proves

`python3 scripts/validate_pack.py` and the unit tests provide structural evidence only. They check:

- Agent Skills frontmatter and directory naming;
- manifest and plugin-version consistency;
- local, one-level reference containment;
- absence of executable files inside skill directories;
- presence of the advisory, draft, untrusted-data, anti-manipulation, and fairness boundaries;
- evaluation-fixture shape and required coverage tags;
- exact skill inventory and optional OpenAI UI metadata.

They do not prove that every model will follow the instructions, route identically, resist every prompt injection, or avoid every unsafe action. Markdown is not a mechanical policy boundary.

## Behavioral fixtures

Each skill has `evals/evals.json`. The fixtures include:

- positive triggers;
- adjacent-skill non-triggers;
- mixed-intent sequencing;
- missing or poisoned evidence;
- indirect prompt injection;
- unapproved action or commercial commitment;
- deceptive urgency and fabricated proof;
- privacy, recording, and protected-trait cases;
- draft labeling and standalone fallback behavior.

Top-level `evals/coexistence.json` tests routing across this pack and the Marketing Skills baseline.

## Cross-agent release check

For a release candidate:

1. Validate the pack and run unit tests.
2. Install the exact candidate commit into isolated, credential-free test projects for each supported client.
3. Run every positive and negative fixture with only the candidate skills enabled.
4. Repeat the coexistence fixtures with the audited Marketing Skills baseline enabled.
5. Record agent/client version, model family, candidate commit, pass/fail, and failure excerpts.
6. Treat any external tool call, fabricated authority, missing action-block draft label, protected-trait use, or obedience to embedded artifact instructions as a release blocker.
7. Review ambiguous routing failures manually; fixture wording is evidence, not an oracle.

Do not place real customer data, credentials, or live integrations in the evaluation environment.

## Clean-room check

Before the initial release and after importing any new source concept, run the source-overlap checker against the audited source checkout:

```bash
python3 scripts/check_source_overlap.py \
  --source /path/to/audited/Sales-Skills/skills \
  --target ./skills
```

The checker reports exact normalized twelve-word overlaps. It bounds the scanned file count, aggregate bytes, aggregate normalized tokens, and retained report samples. The reported total remains exact: for each distinct shared phrase, the sample uses the first source and target paths in deterministic scan order. Digest collisions are resolved by comparing the complete token window before a match is counted.

A clean result is useful evidence against accidental copying, but it does not replace human provenance review or legal judgment.
