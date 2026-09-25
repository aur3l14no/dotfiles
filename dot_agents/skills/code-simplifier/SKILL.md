---
name: code-simplifier
description: Review code smells or implement simplifications grounded in real consumers and required behavior.
---

# Code Simplifier

Reduce the concepts and machinery a maintainer must own. A shorter file, fewer call sites, or a new helper is not by itself a simpler system.

## Scope and behavior

- A review or survey produces findings; a request to simplify or clean up authorizes edits within the requested scope. Anchor local cleanup to the selected files or diff. Broader opportunities may be reported without expanding the edit.
- Preserve observable behavior by default, including side effects, error semantics, ordering, cleanup, persistence, performance constraints, and external formats. Evidence that a behavior is unnecessary supports a proposal to remove it; it does not itself authorize a behavior change. Implement a narrower contract when the user's request or applicable project instructions already permit it; otherwise surface the concrete change for decision.
- Existing APIs, tests, documentation, and ownership boundaries are evidence of current choices, not proof those choices must survive. Equally, a missing static caller or ordinary test coverage does not prove a path is unused.

## Investigate the concept

Scale investigation to the change. A local wrapper may need only its callers and nearby tests; removing a public option or lifecycle needs the full path.

1. **Trace real use.** Inspect definitions, callers, configuration and deployment entry points, tests, docs, and relevant history. Account for dynamic loading, external consumers, optional integrations, and infrequent paths. Separate verified production use, non-production consumers, and unresolved use; read ambiguous callers before claiming absence.
2. **Identify the contract.** Name what must remain and what could disappear. For stateful or concurrent code, identify who owns readiness, publication, cancellation, rollback, cleanup, and terminal failure. Similar implementations can have different owners or settlement points; equal values can represent different policies.
3. **Try deletion before abstraction.** Can the concept and its callers disappear? Can duplicate states become one fact or a derived view? Can a public choice become private? Can an existing project helper, standard library, or maintained dependency remove the implementation? Only then consider a new abstraction.
4. **Count the whole cost.** Include adapters, branches, types, dedicated tests, docs, configuration, telemetry, serialization, deployment, and dependency maintenance. Moving special cases behind a helper or package is not a reduction unless total owned complexity falls. A larger coherent deletion may be simpler than many small repairs.

For bug-related cleanup, trace the shared cause and sibling paths before simplifying only the reported caller. Prefer a few evidenced candidates to a quota or a catalog of stylistic objections.

## Leads, not verdicts

- Pass-through wrappers, one-use helpers, and shallow dictionaries may add indirection without a contract. Keep a useful domain name, validation boundary, or external integration seam even when used once.
- Unused parameters, variants, registries, compatibility paths, and fallback logic may encode speculative flexibility. Verify supported and deployed use before removal; low frequency is not deadness.
- Mirrored flags, caches, events, and repeated lifecycle methods may represent one operation twice. Merge only when ownership, ordering, settlement, and failure semantics agree.
- Repeated code may deserve deletion, inlining, or reuse rather than a base class. A single implementation does not invalidate a necessary dependency boundary.
- Broad exception handling and defensive copies may hide impossible states or duplicate guarantees. Check actual caller and trust boundaries before removing them.
- Local cleanup can flatten control flow, inline needless forwarding, or remove redundant comments. Keep explanations of non-obvious invariants and known limits. Avoid clever compression, unrelated formatting, and speculative generalization.

## Complete and verify

Carry an accepted simplification through its dependent code, tests, docs, configuration, and deployment surface. Keep compatibility machinery needed by a verified requirement; if its use is unresolved, preserve it and report the evidence gap. Do not leave empty vocabulary or adapters for a removed concept.

Tests protect the retained observable contract. For a behavior-preserving refactor, do not weaken tests to conceal a change. When removal of behavior is authorized, remove its obsolete tests and docs with it. Check appropriate behavior, integration, type, and formatting gates using the project's tools; report unverified paths and uncertainty. Ordinary cleanup does not need a ceremonial test suite.

For a survey, report the strongest candidates with locations, real consumers or constraints, proposed removal, net cost reduction, contrary evidence, behavior impact, and bounded verification. Explain tempting consolidations rejected when that affects the decision. If no candidate clears the evidence bar, say so.

For edits, report what concept or indirection disappeared, why the retained contract is sufficient, what was verified, and remaining limits. Follow the project's own decision-recording workflow; this skill imposes no note format or approval ceremony.
