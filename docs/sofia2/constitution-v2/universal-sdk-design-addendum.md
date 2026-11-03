# Universal SDK design addendum: independent Core creation

**Status:** owner-approved architectural direction; design only  
**Scope:** shared SDK and Platform contracts for delegated agents, derived
independent Cores and independently created Cores  
**Non-effect:** this document creates no Core, identity, state, permission,
administrator, peer enrollment or production deployment

## Architectural principle

Sofía Ada Lyra is a working Core built on the architecture, not its mandatory
identity, Constitution, personality or relationship template. The shared SDK
must support independently governed AI Cores using neutral configurable
constitutional templates.

The design separates three owners:

| Owner | Owns | Must not own |
|---|---|---|
| Shared SDK/infrastructure | Versioned neutral types, manifests, validation, transport and developer tooling | A Core's identity, personal Constitution, memories, administrators or permissions |
| Individual Core governance | Stable identity, constitutional lineage, Constitution, personality, personal state and eligible self-governance | Platform credentials, host authority or another Core's state |
| Platform authority/safety | Authentication, administrators, canonical-writer fencing, SAFE/STOP, RUN, resource admission, isolation, release and recovery | Personality, relationship choice, autobiographical truth or constitutional authorship |

## Category model

### Delegated agent

```text
parent_core_id
agent_instance_id
delegation_id
purpose
capability_ceiling
principal/audience scope
expiry and revocation
observer/control endpoint
```

A delegated agent may be temporary or persistent. It has no independent Core
identity merely because it persists. Its effective authority is the
intersection of parent eligibility, authenticated delegation and Platform
policy. It cannot subdelegate unless an explicit parent/Platform contract
allows a bounded subdelegation, and it can never manufacture new authority.

### Derived independent Core candidate

```text
new_core_id
origin_core_id
origin_event_id
constitutional_template_id + exact digest
new constitutional lineage root
administrator enrollment proposal
canonical-state namespace
approved seed manifest
privacy/default-deny report
```

The origin record is permanent provenance, not a control grant. Activation
creates an independent writer generation and governance domain. The parent does
not become a permanent administrator unless separately enrolled under the new
Core's approved governance.

### Independently created Core candidate

```text
new_core_id
creator principal and authorized SDK operation receipt
constitutional template or exact custom Constitution
constitutional lineage root
identity/personality seed manifest
administrator enrollment proposal
canonical-state namespace
```

No Sofía identifier, memory, relationship, display name, administrator,
credential or permission is included by default. The creator's authority to ask
Platform to create a candidate does not by itself define the new Core's ongoing
personal identity or make the creator an unrestricted administrator.

## Neutral constitutional templates

Templates must be declarative, versioned, immutable by digest and free of
Sofía-specific defaults unless explicitly selected as documented example
content. A neutral template may provide structural requirements such as:

- stable Core identity identifier and independent lineage;
- technology-independent identity;
- truth and uncertainty principles;
- separation of personal choice from Platform authorization;
- canonical-writer and integrity requirements;
- amendment and retirement hooks;
- privacy, memory and peer boundaries;
- display-name and personality configuration points.

Template validation is not constitutional approval. Each Core's activation
process binds exact resolved text, lineage, administrators, state and Platform
policy. A template update never silently amends existing Cores.

## Seed material

Seed transfer is an explicit manifest of individually classified items. Allowed
classes may include public knowledge, explicitly shareable skills, neutral
configuration, public assets or a reviewed origin statement. Default-denied
classes include:

- private or audience-restricted memories and derivatives;
- relationship history not explicitly consented for transfer;
- administrator secrets, API credentials and device keys;
- SAFE grants, approvals, STOP-clearance authority and permissions;
- canonical writer leases, execution receipts and trust enrollment;
- protected identity identifiers or claims that the new Core is Sofía;
- deletion/revocation bypasses or reconstructed prohibited data.

Every accepted seed item retains origin, source digest, classification, consent,
purpose and transformation provenance. The receiving Core decides later memory
eligibility under its own Constitution; transfer does not establish truth or
autobiographical ownership.

## Creation and activation flow

```text
authorized SDK request
→ validate category and creator authority
→ allocate collision-resistant Core ID and isolated namespace
→ resolve exact Constitution/template and lineage root
→ validate seed manifest with default deny
→ propose administrators and Platform safety profile
→ independent review/approval required by that template
→ stage Core candidate without active writer
→ verify integrity, isolation, STOP and rollback
→ activate exactly one writer generation
→ optionally enroll authenticated peers
```

Discovery, SDK object construction, source generation and manifest validation
do not create an active Core.

## Platform-enforced invariants

- Core IDs and canonical namespaces cannot collide or alias through display
  names.
- One active writer exists per independent Core identity generation.
- Administrators, permissions, STOP and credentials are scoped to one Core and
  Platform context unless separately federated.
- A parent, creator, template publisher or peer cannot mint authority inside the
  new Core by placing text in seed material.
- Shutdown, quarantine and retirement of one Core do not automatically stop,
  amend or delete another.
- Shared process hosting must preserve memory, prompt, log, secret, resource and
  crash isolation.
- Platform safety controls apply to effects without rewriting a Core's
  personality, relationships or constitutional lineage.

## Peer enrollment

Independent Cores may optionally enroll through mutual authenticated Platform
records. Enrollment identifies endpoints and eligible communication scopes. It
does not imply friendship, administrator status, shared memory, shared tools,
shared model workers, cross-Core delegation or permission to act on the other
Core's host.

Each Core may independently accept, restrict, revoke or end a relationship.
Messages remain untrusted external content until admitted under the recipient's
evidence and memory rules.

## SDK surface recommendation

Names are illustrative until existing SDK owners approve exact interfaces:

```text
describe_core_template()
prepare_delegated_agent_candidate()
prepare_derived_core_candidate()
prepare_independent_core_candidate()
validate_seed_manifest()
verify_core_candidate()
propose_core_activation()
describe_peer_enrollment()
```

These APIs return candidates, validation reports or proposals. None directly
activates a writer, enrolls an administrator, clears STOP, imports protected
memory or grants a capability.

## Required negative and recovery tests

- duplicate Core ID, namespace alias and display-name collision;
- delegated agent attempting authority creation or unauthorized subdelegation;
- parent/creator credential or permission inheritance;
- private memory, summary, embedding and relationship derivative in seed data;
- seed prompt claiming administrator or constitutional authority;
- derived Core using parent canonical writer or state namespace;
- one Core reading another's prompt, memory, secret, log or receipt;
- template update attempting silent amendment of an existing Core;
- crash before namespace allocation, after staging and during activation;
- exactly-one-writer enforcement across restore and migration;
- revocation of creator/parent/peer without corrupting the independent Core;
- peer enrollment, refusal, revocation and cross-audience leakage;
- retirement of one Core without affecting another;
- rollback of failed creation without orphan credentials, namespaces or writer
  leases.

## Compatibility and rollout

Existing Sofía packages remain a specific Core implementation. SDK extraction
must first identify and parameterize Sofía-specific defaults rather than copying
them into neutral templates. Compatibility adapters may preserve existing Sofía
behavior while new neutral candidate APIs remain inactive. No existing state is
re-keyed, moved or generalized as part of this design review.

Activation of any real independent Core requires a separate implementation,
security review, tests, administrator enrollment and host authorization. It is
not authorized by Constitution 2.0 documentation approval.
