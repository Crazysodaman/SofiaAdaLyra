# OpenCode Development Integration

## Purpose

OpenCode is the intended external implementation executor for Sofía Ada Lyra.

It is not Sofía's identity, cognitive system, authority system, or source of truth.

## Responsibilities

### Sofía

Sofía is responsible for:

- understanding the codebase
- analyzing implementation and relationships
- identifying affected components
- identifying relevant tests
- forming change plans
- determining whether a requested operation is authorized
- evaluating implementation evidence
- verifying resulting behavior

### OpenCode

OpenCode is responsible for mechanical development work after the appropriate approval boundary:

- editing source files
- creating tests
- running tests
- inspecting test failures
- iterating on implementation
- reporting implementation results

### Human

The human remains responsible for consequential development approval during this stage of the project.

Human review is especially important before:

- broad architectural changes
- consequential filesystem changes
- Git commits
- repository publication
- future remote-system operations

## Development Flow

The intended workflow is:

    Sofía
      |
      v
    Understand
      |
      v
    Analyze
      |
      v
    Plan
      |
      v
    Human approval
      |
      v
    Authority
      |
      v
    OpenCode
      |
      +--> Edit
      |
      +--> Test
      |
      +--> Diagnose
      |
      +--> Iterate
      |
      v
    Evidence
      |
      v
    Sofía verification

## Current Boundary

PKG-DEV planned Waves 1–5 source controls are now on `main` via PRs #99/#103. Sofía has a bounded OpenCode execution adapter plus base-SHA verification, exact workspace/diff scope checks, detached Git worktrees, targeted-test evidence, reviewed patch application and guarded rollback. Applying, committing and pushing remain separate authorization boundaries.

This is **not** yet proof of a live autonomous OpenCode runtime session on the production Sofía host. End-to-end KNOW→DEV→VERIFY self-tooling, consequential publication/deployment/restart, and production remote-system operations remain separately gated.

## Git

OpenCode may inspect Git state.

OpenCode itself does not receive blanket remote-push authority. The DEV workflow exposes push only as a separate explicitly authorized operation.

Git commits and pushes remain distinct authorization boundaries.

Published history must not be rewritten without explicit human direction.

## Verification

A successful OpenCode run is not itself evidence that a change is correct.

Verification requires:

1. targeted tests
2. failure diagnosis where needed
3. broader test execution
4. review of the resulting diff
5. confirmation that the change satisfies the intended contract

## Relationship to Codebase Analysis

Sofía's codebase understanding and analysis system remains independent.

OpenCode may perform its own repository analysis to accomplish development work, but Sofía must not become dependent on OpenCode for understanding her own codebase.

OpenCode analysis can be treated as development evidence to review, not automatically as authoritative fact.

## Future

A later batch may introduce a controlled OpenCode capability:

    Sofía
      |
      v
    Capability Gateway
      |
      v
    Authority
      |
      v
    OpenCode Adapter
      |
      v
    OpenCode

That capability must define:

- permitted operations
- workspace scope
- approval requirements
- evidence returned to cognition
- failure behavior
- cancellation behavior
- Git boundaries
- recovery behavior

Until that capability exists, OpenCode remains external development tooling.