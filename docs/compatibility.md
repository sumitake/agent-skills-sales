# Compatibility and routing

## Portability contract

Each directory under `skills/` conforms to the open Agent Skills shape:

- required `SKILL.md` with portable YAML frontmatter;
- local resources referenced one level below the skill root;
- no cross-directory relative links;
- no scripts, tool allowlists, network dependency, or imported skill content;
- optional `agents/openai.yaml` UI metadata that other clients may ignore.

A client that understands only `name`, `description`, and the Markdown body still receives the full capability. Repository-level Claude plugin metadata is packaging convenience, not a runtime dependency.

## Coexistence matrix

The matrix records primary ownership when this pack and Marketing Skills are installed together.

| Immediate requested outcome | Primary skill | Boundary |
| --- | --- | --- |
| Prepare or debrief a named buyer conversation | `sales-discovery` | Not list building or aggregate customer research |
| Understand or answer a value, fit, trust, risk, or timing concern with no concrete trade | `sales-objection-handling` | Numeric or contractual exchanges route to negotiation |
| Design a discount, scope exchange, payment change, contract term, or concession | `sales-negotiation` | Company-wide pricing or offer architecture remains upstream |
| Assess whether one named opportunity should advance, pause, or stop | `sales-qualification` | List generation and CRM scoring-system design remain upstream |
| Inspect a named or bounded cohort of won, lost, stalled, or forecasted deals | `sales-deal-review` | CRM architecture and broad market research remain upstream |
| Find, enrich, and prioritize a prospect list | Marketing Skills `prospecting` | This pack can qualify a supplied named opportunity afterward |
| Write first-touch cold outbound or a cold sequence | Marketing Skills `cold-email` | This pack may draft a deal-specific follow-up after analysis |
| Create reusable decks, playbooks, battlecards, or objection collateral | Marketing Skills `sales-enablement` | This pack produces evidence-grounded inputs for the asset |
| Design lifecycle stages, lead scoring, routing, CRM workflows, or deal desk systems | Marketing Skills `revops` | This pack never mutates those systems |
| Set portfolio price levels, tiers, packaging, value metrics, or offer architecture | Marketing Skills `pricing` or `offers` | This pack handles a specific authorized deal negotiation |
| Research an external competitor or publish comparison content | Marketing Skills `competitor-profiling` or `competitors` | Deal review uses only supplied or separately inspected evidence |
| Run aggregate customer interviews or voice-of-customer research | Marketing Skills `customer-research` | Discovery focuses on a buyer conversation in a sales opportunity |

## Price-friction precedence

Price language alone does not determine routing.

- “Help me understand why they think this is expensive” routes to `sales-objection-handling`.
- “Should we trade 10% off for annual prepayment?” routes to `sales-negotiation`.
- A request containing both is handled sequentially: clarify the concern, then structure the exchange.

## Mixed intents

Choose the skill matching the immediate decision or deliverable. Address that outcome first. Then invoke a second compatible skill sequentially when available, or provide no more than three bullets of local fallback guidance. Do not force the user to repeat an adjacent request, and do not run overlapping reasoning tracks without an explicit sequence.

## Standalone behavior

References to neighboring skills are optional routing hints. No skill reads another skill directory or assumes a neighbor is installed. When this pack runs alone:

1. Each skill completes its named job from user-provided or independently inspected evidence.
2. Missing evidence is labeled and paired with a validation step rather than invented.
3. An adjacent request receives a bounded fallback, not a broken link or fabricated capability.
4. External action remains out of scope even if the host has mutation tools.

## Tested coexistence baseline

The initial routing review used `coreyhaines31/marketingskills` release `v2.11.0`, commit `8907942a47045c387ddf58e5b1cf03fc435a1cd7`. Marketing Skills is optional and may evolve. This pack pins no runtime dependency on its names or content; future releases should rerun the coexistence fixtures against the current upstream catalog.
