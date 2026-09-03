## Summary

Describe the user-visible outcome and the narrow scope of this change.

## Source and provenance

- Concept source, exact commit, and license, or `N/A` for an original maintenance change:
- Independent-rewrite and clean-room evidence, when applicable:

## Routing and safety

- Primary trigger and adjacent non-triggers:
- Standalone behavior when optional neighboring packs are absent:
- Advisory, authority, draft, consent, fairness, and untrusted-data boundaries affected:

## Validation

- [ ] `python3 scripts/validate_pack.py`
- [ ] `python3 -m unittest discover -s tests -v`
- [ ] Official Agent Skills validator run for every changed skill
- [ ] Relevant behavioral and coexistence fixtures reviewed or executed
- [ ] Clean-room overlap check run when a source concept changed

## Public-repository checklist

- [ ] No credentials, customer data, private sales artifacts, or exploit details are included
- [ ] Third-party action references are pinned to full commit SHAs
- [ ] User-visible changes are recorded in `CHANGELOG.md`
- [ ] No executable, network, integration, or hidden mutation surface was added to a skill
- [ ] Documentation and local links were checked
