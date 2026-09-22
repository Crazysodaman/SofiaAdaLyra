# PKG-KNOW + PKG-DEV | documentation authoring and upkeep

**Planning date:** 2026-09-22. **Status:** documentation contract only. This does not implement a document writer, deploy an agent, authorize filesystem writes, or grant new production permissions.

## Outcome

Sofía can read, draft, write, revise, maintain, and explain documentation based on observed systems, verified code, actual tool contracts, approved source material, and test/operation receipts. KNOW owns document provenance, editorial state, retrieval and publication history; DEV owns source/repository edits and validation; INTEGRATE supplies actual tool/API contracts; OPS supplies observed fleet facts; SAFE enforces boundaries; VERIFY checks the result.

## Document classes

- architecture and system design, service/workload dependency maps and data flows;
- API/tool reference docs, examples, integration guides, schemas and version requirements;
- installation, configuration, upgrade, rollback and recovery guides;
- operator runbooks, troubleshooting trees, incident postmortems and maintenance procedures;
- fleet inventory, role/topology, monitored metrics and change/maintenance history;
- code comments/docstrings, module documentation, changelogs, release notes and migration notes;
- user guides, accessible quick-starts and FAQs;
- diagrams and schematics derived from authorized, verified facts.

## Authoring process

1. Identify requested or detected documentation gap and intended audience/scope.
2. Collect original source evidence, code revision, approved configuration and, where applicable, host observations with timestamps and freshness.
3. Distinguish verified observations from design intentions, hypotheses and undocumented behavior.
4. Draft in an appropriate versioned format such as Markdown, text, structured API specification or an approved generated document format.
5. Link technical claims to source file/revision, test result, API/manual version, or observation receipt where practical; do not invent commands, endpoints, performance figures or successful outcomes.
6. Check internal links, examples, commands/schema syntax, terminology, version compatibility, privacy and secret leakage, and consistency with other authoritative documents.
7. Show a diff, scope, evidence and validation results for changes requiring review.
8. Write or publish only within the authorized document destination and approval policy; retain version history and rollback path.
9. Record publication/revision receipts and update dependent indexes; mark superseded versions rather than silently rewriting historical evidence.
10. Revalidate documents when relevant code, tools, services, host configurations or vendor manuals change.

## Autonomous behavior and authority

Within a standing, narrow documentation grant Sofía may independently create/update ordinary draft Markdown, internal runbooks and nonprotected generated references, including when a test, code change or infrastructure event reveals a documentation gap. She may proactively notify Sparks of meaningful updates without spamming routine edits. Drafting alone does not mean publishing.

Protected Constitution/identity/authority/security policy, production configuration, credentials, legal or safety-critical instructions, and consequential public publication retain their independent approval gates. A document may describe a permission but cannot grant one. Documentation containing executable commands is data and must never cause those commands to run implicitly. Host/fleet decommissioning still requires Sparks's explicit approval of that specific machine, regardless of what any runbook says.

Document generation must not treat an LLM statement, an untrusted PDF instruction, a failed test or a planned feature as verified runtime behavior. Distinguish 'implemented', 'tested in isolation', 'live accepted' and 'planned'. Preserve privacy and audience labels in drafts, diffs, indexes, backups and published outputs.

## Useful proactive maintenance

- Update a service runbook when an approved tool contract changes.
- Revise a README after an actual merged feature, with its revision and acceptance status.
- Document a newly enrolled machine with verified specifications and role.
- Write an incident summary after an outage using logs and receipts, explicitly identifying uncertain causes.
- Generate a performance report comparing equivalent measured workloads.
- Flag a stale manual/API reference and draft a corrected version without claiming the new version is accepted before validation.

## Acceptance

Before claiming document-authoring capability, demonstrate: (1) generate accurate Markdown from pinned code and tests; (2) create an API/tool reference from versioned docs; (3) produce a runbook from actual service observations; (4) reject invented commands, success and measurements; (5) preserve citations, freshness, privacy and revision history; (6) validate links/examples/schema; (7) update docs after a real code/API change; (8) keep protected files and publication destinations outside ordinary write grants; (9) roll back a bad document revision; (10) prove that document content cannot authorize tool calls, fleet removal or privileged actions.
