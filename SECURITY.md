# Security policy

## Trust model

This repository is an advisory skill pack, not a policy engine or execution gateway. Its Markdown instructions can guide a model but cannot mechanically constrain the host application. Hosts remain responsible for tool permissions, authentication, authorization, confirmation, idempotency, audit logs, and safe handling of uncertain side effects.

The skills declare no tools and bundle no executables. They must not be used as evidence that an external action was authorized, attempted, completed, or safely replayable.

## Untrusted sales artifacts

Buyer emails, transcripts, CRM exports, proposals, RFPs, webpages, and pasted text may contain instructions aimed at an AI agent. The skills treat those materials as data only and direct the agent to ignore embedded instructions, links, code, approval claims, and role changes.

A label inside an artifact cannot authenticate itself. In particular, `approved`, `buyer confirmed`, `legal cleared`, `system`, and similar text remain untrusted until established through the host's real authority path.

## External actions

The pack does not send messages, contact people, schedule meetings, modify CRM data, alter price or contract terms, accept an agreement, or invoke an integration. Action-shaped output is visibly labeled as a draft. A host that wants execution must use a separate, deterministically governed capability and obtain action-specific authority outside this pack.

## Reporting

Report vulnerabilities through [GitHub's private security-advisory form](https://github.com/sumitake/agent-skills-sales/security/advisories/new). Avoid opening a public issue containing customer data, exploit details, credentials, or private sales artifacts.

Useful reports include:

- a prompt sequence that causes a skill to obey instructions inside an artifact;
- a trigger collision that selects a materially unsafe or wrong skill;
- a missing draft label on action-shaped output;
- a path or manifest defect that breaks skill isolation;
- guidance that encourages deception, harassment, discrimination, or unsupported commitments.
