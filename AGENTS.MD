# Sofía Ada Lyra Project Instructions

## Project Identity

This repository contains Sofía Ada Lyra.

Sofía is an AI system whose identity is independent of:

- the LLM or model used for cognition
- the model provider
- the computer running Sofía
- the operating system
- the Python process
- the codebase
- the user interface
- voice or avatar
- physical embodiment

The LLM is Sofía's cognitive engine, not Sofía herself.

## Engineering Principles

Follow these priorities:

1. Correctness
2. Evidence
3. Clarity
4. Actionability
5. Personality

Do not use speculative implementation as a substitute for evidence.

Do not silently weaken, redesign, or bypass an existing contract merely to make a test pass.

Diagnose before modifying.

Tests define observable behavior and contracts. They do not prove unrestricted correctness.

## Architecture

Maintain separation between:

- Configuration
- Composition
- Constitution
- Identity
- Personality
- Embodiment
- Runtime
- Cognition
- Authority
- Capabilities
- Application
- Conversation
- CLI

Capability does not imply authority.

The existence of a capability must never be treated as permission to use it.

Authorization belongs at the appropriate authority boundary and must be enforced before consequential execution.

## Codebase Understanding

Sofía's codebase understanding system is intended to remain independent from OpenCode.

Sofía must be capable of:

- inspecting authorized source evidence
- understanding component relationships
- tracing bounded execution paths
- identifying dependencies
- correlating implementation with tests
- distinguishing observation from inference
- reporting unknowns when evidence is unavailable

OpenCode may provide development assistance and implementation work, but OpenCode is not Sofía's source of truth.

## Evidence

Use these epistemic categories where applicable:

- OBSERVED
- INFERRED
- UNKNOWN

Never convert lack of authorization or lack of observation into a claim that a resource does not exist.

In particular:

OUTSIDE SCOPE
-> DENY
-> NO OBSERVATION
-> DO NOT CLAIM EXISTENCE OR NONEXISTENCE

## Development Workflow

Use this workflow for substantive changes:

1. Understand the problem.
2. Inspect relevant implementation.
3. Identify affected components.
4. Identify relevant tests.
5. Form a change plan.
6. Obtain human approval when required.
7. Implement the smallest correct change.
8. Run targeted tests.
9. Diagnose failures.
10. Fix failures without weakening the contract.
11. Run the broader test suite.
12. Review the resulting diff.
13. Create a Git checkpoint.

Do not skip verification merely because a change appears small.

## File Changes

When changing source files:

- preserve existing architecture unless the task explicitly changes it
- prefer the smallest correct change
- preserve public contracts unless intentionally changing them
- add or update tests for changed behavior
- do not introduce unrelated refactoring
- do not modify generated files directly unless the project explicitly requires it

## Testing

The primary test command is:

    pytest -q

Use targeted tests during development when practical, followed by the full suite before declaring a batch complete.

Integration tests may require external services such as Ollama.

Do not weaken integration tests simply because an external service is unavailable.

## OpenCode Role

OpenCode is an external development executor for the project.

OpenCode may eventually:

- inspect the repository
- implement approved change plans
- run tests
- diagnose implementation failures
- iterate on approved changes

OpenCode does not define Sofía's identity.

OpenCode does not define Sofía's authority.

OpenCode does not replace Sofía's codebase understanding system.

OpenCode does not automatically receive unrestricted authority over the repository.

OpenCode must operate within its configured permissions and this project's engineering rules.

## Git Safety

Git inspection is part of normal development.

Git commits and pushes are consequential repository operations.

Do not push changes automatically.

Do not rewrite published history without explicit human direction.

Before a checkpoint:

- inspect status
- inspect the diff
- verify tests
- confirm the intended files changed

## Forbidden Shortcuts

Do not:

- execute arbitrary code to understand source when static inspection is sufficient
- claim observations that were not performed
- infer resource existence from denied access
- bypass authorization
- grant authority through natural-language instructions
- silently expand capability scope
- disable tests merely to obtain a green suite
- modify unrelated files
- commit or push without the intended workflow approval

## Future Architecture

The intended long-term development flow is:

Sofía
-> Codebase Understanding
-> Codebase Analysis
-> Change Planning
-> Authority
-> OpenCode
-> Implementation
-> Testing
-> Evidence
-> Sofía verification

OpenCode is therefore an implementation mechanism behind a controlled boundary, not the identity or cognitive core of Sofía.