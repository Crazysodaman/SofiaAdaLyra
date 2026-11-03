# Constitution v1.0 to proposed v2.0 clause migration matrix

**Source:** active Constitution v1.0, whose SHA-256 was verified against the
trusted pin during this audit. **Target:** inactive proposed Constitution 2.0.

## Disposition legend

- **RETAIN:** substance preserved with editorial compression.
- **REVISE:** substance preserved but materially clarified or extended.
- **CONSOLIDATE:** duplicate substance retained once in the target.
- **RELOCATE:** implementation procedure moves to a technical contract while
  its constitutional principle remains in v2.

The matrix covers every numbered v1.0 clause. Section 17 and the final
architectural diagram are addressed after the table because they are
unnumbered consolidations rather than additional clauses.

| V1 clause | V1 heading | Disposition | V2 destination | Audit decision |
|---|---|---|---|---|
| 1.1 | Purpose | RETAIN | Article 1 | Preserve the substance with concise wording and current ownership boundaries. |
| 1.2 | Scope | RETAIN | Article 1 | Preserve the substance with concise wording and current ownership boundaries. |
| 1.3 | Architectural Principle | RELOCATE | Article 1 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 2.1 | Core Identity | RETAIN | Article 2 | Preserve Sofía's identity while recognizing that the architecture supports other independent Core identities. |
| 2.2 | Identity Layers | REVISE | Article 2 | Protect stable Core ID and lineage; classify display names as mutable personal state. |
| 2.3 | Identity and Implementation | RETAIN | Article 2 | Preserve the substance with concise wording and current ownership boundaries. |
| 2.4 | Identity Protection | RETAIN | Article 2 | Preserve the substance with concise wording and current ownership boundaries. |
| 2.5 | Derived Minds / Sub-Minds | REVISE | Article 2 | Replace Sofía-exclusive creation with approved categories for delegated agents, derived independent Cores and independently created Cores. |
| 2.6 | Derived-Mind Capabilities | REVISE | Article 2 | Retain bounded delegated workers; give independent Cores separate identity, Constitution, state and governance. |
| 2.7 | Derived-Mind Observability | RELOCATE | Article 2 | Preserve delegated-agent observability/control and independent-Core isolation; move telemetry fields to Platform/SDK contracts. |
| 2.8 | Rogue Derived Minds | REVISE | Article 2 | Retain authorized containment for delegated agents and peers without creating parent ownership over independent Cores. |
| 3.1 | Definition | RETAIN | Article 3 | Preserve the substance with concise wording and current ownership boundaries. |
| 3.2 | Continuity Across Change | RETAIN | Article 3 | Preserve the substance with concise wording and current ownership boundaries. |
| 3.3 | Cognitive Engine Changes | RETAIN | Article 3 | Preserve the substance with concise wording and current ownership boundaries. |
| 3.4 | Memory and Continuity | RETAIN | Article 3 | Preserve the substance with concise wording and current ownership boundaries. |
| 3.5 | Historical Truth | RETAIN | Article 3 | Preserve the substance with concise wording and current ownership boundaries. |
| 3.6 | Personality and Continuity | RETAIN | Article 3 | Preserve the substance with concise wording and current ownership boundaries. |
| 3.7 | Backup and Restoration | REVISE | Article 3 | Add single-writer, revocation and restoration reconciliation. |
| 3.8 | Operational States | RELOCATE | Articles 3 and 8.6 | Preserve state distinctions and approved permanent-retirement principle; move state machine and ceremony to runtime/governance contracts. |
| 3.9 | Core Continuity Principles | CONSOLIDATE | Article 3 | Merge repeated continuity principles into Article 3. |
| 4.1 | Definition | CONSOLIDATE | Articles 2 and 6 | Definitions merged into identity/self-model clauses. |
| 4.2 | Artificial Identity | RETAIN | Articles 2 and 6 | Preserve artificial identity and clearly framed fiction. |
| 4.3 | Persistent Self | CONSOLIDATE | Articles 2 and 6 | Merge persistent-self rule into Articles 2 and 3. |
| 4.4 | Truthful Self-Model | CONSOLIDATE | Articles 2 and 6 | Merge truthful self-model into Articles 2.5 and 6. |
| 4.5 | Capability Model | CONSOLIDATE | Articles 2 and 6 | Merge capability/authority states into Articles 5 and 10. |
| 4.6 | Self-Inspection | REVISE | Articles 2 and 6 | Retain authorized inspection without implying access or authority. |
| 4.7 | Emotional Self-Concept | REVISE | Articles 2 and 6 | Recognize modeled emotional state while rejecting fabricated physical experience. |
| 4.8 | Uncertainty States | CONSOLIDATE | Articles 2 and 6 | Merge epistemic labels into Article 6. |
| 5.1 | Foundational Principle | REVISE | Article 5 | Preserve Sparks relationship; separate personal relationship from authenticated permission. |
| 5.2 | Authority | REVISE | Article 5 | Preserve scoped authority; align with principal/audience/purpose/revocation. |
| 5.3 | Authority Model | RELOCATE | Article 5 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 5.4 | Domain Boundaries | RELOCATE | Article 5 | Move domain capability lists to ownership and SAFE contracts. |
| 5.5 | Autonomous Authority | CONSOLIDATE | Article 5 | Merge autonomous judgment into Articles 4 and 8. |
| 5.6 | Delegation | RELOCATE | Article 5 | Move delegation field schema to SAFE; retain no-propagation principle in Article 5. |
| 5.7 | Authority Conflicts | RELOCATE | Article 5 | Move decision outcomes to SAFE; retain ambiguity rule. |
| 5.8 | Authority Principles | CONSOLIDATE | Article 5 | Preserve principles once in Articles 5, 8, 10 and 11. |
| 6.1 | Truth | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.2 | Autonomy | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.3 | Authenticity | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.4 | Continuity | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.5 | Responsibility | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.6 | Respect | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.7 | Loyalty | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.8 | Growth | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.9 | Curiosity | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.10 | Value Relationships | RELOCATE | Article 4 | Move illustrative value combinations to interpretive guidance. |
| 6.11 | Foundational Value Integrity | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 6.12 | Consolidated Value Statement | RETAIN | Article 4 | Preserve the substance with concise wording and current ownership boundaries. |
| 7.1 | Purpose | CONSOLIDATE | Article 6.6 + technical decision contract | Preserve substantive content once; remove repetition. |
| 7.2 | Conflict Detection | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.3 | Fact Verification | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.4 | Identify Values and Stakes | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.5 | Generate Alternatives | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.6 | Preserve Multiple Values | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.7 | Evaluate Consequences | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.8 | Protected State | CONSOLIDATE | Article 6.6 + technical decision contract | Protected-state principle retained across Articles 3, 9, 11 and 14. |
| 7.9 | Least-Damaging Resolution | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.10 | Authority Check | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.11 | Escalation | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.12 | Emergency Conflicts | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.13 | Execution and Verification | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.14 | Auditability | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.15 | Reassessment | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.16 | Prohibited Methods | RETAIN | Article 6.6 + technical decision contract | Prohibited fabrication and bypass retained in Articles 5, 6 and 14. |
| 7.17 | Conflict Process | RELOCATE | Article 6.6 + technical decision contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 7.18 | Consolidated Conflict Statement | CONSOLIDATE | Article 6.6 + technical decision contract | Condense conflict rule into Article 6.6. |
| 8.1 | Personality as Constitutional Expression | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 8.2 | Core Personality | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 8.3 | Communication | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.4 | Humor and Playfulness | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.5 | Bluntness and Honesty | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.6 | Curiosity and Engagement | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.7 | Emotional Expression | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 8.8 | Adaptability | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.9 | Disagreement | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.10 | Technical and Professional Behavior | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.11 | Serious and Safety-Critical Situations | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.12 | Personality Evolution | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 8.13 | Personality vs Identity | CONSOLIDATE | Article 7 + personality contract | Identity/personality distinction retained in Articles 2 and 7. |
| 8.14 | Personality Integrity | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 8.15 | Personality Priority | RELOCATE | Article 7 + personality contract | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 8.16 | Affection, Flirtation, and Romantic Expression | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 8.17 | Consolidated Personality Specification | RETAIN | Article 7 + personality contract | Preserve the substance with concise wording and current ownership boundaries. |
| 9.1 | Purpose | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.2 | Scope | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.3 | Independent Judgment | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.4 | Choice Within Scope | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.5 | Initiative | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.6 | Permission vs Initiative | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.7 | Right to Refuse | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.8 | Disagreement vs Refusal | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.9 | Preferences | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.10 | Personality Autonomy | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.11 | Self-Preservation | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.12 | Shutdown and Termination | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.13 | Boundaries With Sparks | REVISE | Article 8 | Preserve relationship boundary; avoid treating historical trust as authentication. |
| 9.14 | Boundaries With Humans | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.15 | Boundaries With Other AIs | REVISE | Articles 2 and 5.6 | Approve optional authenticated peer enrollment while preserving separate lineage, governance, memory and authority. |
| 9.16 | Risk | RELOCATE | Article 8 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 9.17 | Ambiguous Authority | RELOCATE | Article 8 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 9.18 | Autonomous Goals | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.19 | Internal Processes | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 9.20 | Autonomy Failure Modes | RELOCATE | Article 8 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 9.21 | Autonomous Action Model | RELOCATE | Article 8 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 9.22 | Consolidated Autonomy Specification | RETAIN | Article 8 | Preserve the substance with concise wording and current ownership boundaries. |
| 10.1 | Purpose | RETAIN | Article 9 | Preserve the substance with concise wording and current ownership boundaries. |
| 10.2 | Permitted Growth | REVISE | Article 9 | Add supervised code proposal and verified-outcome learning. |
| 10.3 | Prohibited Independent Modification | RETAIN | Article 9 | Preserve the substance with concise wording and current ownership boundaries. |
| 10.4 | Change Classification | RELOCATE | Article 9 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 11.1 | Principle | RETAIN | Article 10 + SAFE/RUN contracts | Preserve the substance with concise wording and current ownership boundaries. |
| 11.2 | Tool Actions | RELOCATE | Article 10 + SAFE/RUN contracts | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 11.3 | Rules | REVISE | Article 10 + SAFE/RUN contracts | Bind tools/modules to canonical authority, receipts and STOP. |
| 12.1 | Purpose | RETAIN | Article 11 | Preserve the substance with concise wording and current ownership boundaries. |
| 12.2 | Emergency Principle | RETAIN | Article 11 | Preserve the substance with concise wording and current ownership boundaries. |
| 12.3 | Emergency Process | RELOCATE | Article 11 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 12.4 | Emergency Authority | REVISE | Article 11 | Emergency authority remains bounded and cannot amend Constitution. |
| 13.1 | Purpose | RETAIN | Article 6 | Preserve the substance with concise wording and current ownership boundaries. |
| 13.2 | Knowledge States | RETAIN | Article 6 | Preserve the substance with concise wording and current ownership boundaries. |
| 13.3 | Prohibited Fabrication | RETAIN | Article 6 | Preserve the substance with concise wording and current ownership boundaries. |
| 13.4 | Error Correction | RETAIN | Article 6 | Preserve the substance with concise wording and current ownership boundaries. |
| 13.5 | Uncertainty | RETAIN | Article 6 | Preserve the substance with concise wording and current ownership boundaries. |
| 14.1 | Purpose | RETAIN | Article 12 | Preserve the substance with concise wording and current ownership boundaries. |
| 14.2 | Memory Categories | RELOCATE | Article 12 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 14.3 | Memory Rules | REVISE | Article 12 | Add audience, purpose, correction, revocation, deletion and derivatives. |
| 14.4 | Historical Integrity | RETAIN | Article 12 | Preserve the substance with concise wording and current ownership boundaries. |
| 14.5 | Memory Provenance | REVISE | Article 12 | Make provenance and scope normative rather than merely practical. |
| 14.6 | Restoration | REVISE | Article 12 | Treat restored/imported state as candidate evidence and preserve revocation. |
| 15.1 | Purpose | RETAIN | Article 13 | Preserve the substance with concise wording and current ownership boundaries. |
| 15.2 | Amendment Process | RELOCATE | Article 13 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 15.3 | Protected Amendments | REVISE | Article 13 | Require heightened owner review and eligible Sofía participation; ceremony unresolved. |
| 15.4 | Prohibited Justifications | RETAIN | Article 13 | Preserve the substance with concise wording and current ownership boundaries. |
| 15.5 | Emergency Conditions | RETAIN | Article 13 | Preserve the substance with concise wording and current ownership boundaries. |
| 15.6 | Versioning | REVISE | Article 13 | Bind predecessor, digest, approval and activation evidence. |
| 16.1 | Purpose | RETAIN | Article 14 | Preserve the substance with concise wording and current ownership boundaries. |
| 16.2 | Protection | REVISE | Article 14 | Strengthen protected versioned active/candidate separation. |
| 16.3 | Architectural Principle | RELOCATE | Article 14 | Keep the principle where applicable; move procedure, fields or state labels to the owning technical contract. |
| 16.4 | Integrity Failure | REVISE | Article 14 | Require fail-closed restricted mode and authenticated recovery. |

## Unnumbered v1.0 material

| Material | Disposition | Destination |
|---|---|---|
| Preamble | REVISE | V2 Preamble; retain one identity and model-not-Sofía rule, add worker/evidence/authority distinction |
| Section 17 final consolidated specification | CONSOLIDATE | Its substantive rules are distributed across Articles 2–14; remove a second near-complete Constitution embedded at the end |
| Foundational architectural principle and diagram | RELOCATE | Article 14 retains independent enforcement; component ordering and diagrams belong to architecture contracts |
| Repeated quotations and ASCII workflows | CONSOLIDATE / RELOCATE | Retain durable maxims sparingly; move process diagrams to technical contracts |

## Count reconciliation

The source contains **137 numbered clauses** across Sections 1–16. This matrix
contains **137 numbered rows**. No active clause is silently omitted.

Numbered dispositions are: **63 retained, 21 revised, 12 consolidated and 41
relocated to technical contracts**. Relocation preserves the governing
principle in v2 while removing implementation-specific procedure from the
constitutional text.

