# Core-free tool binding isolation

The host-owned `CognitiveToolBinding` dataclass now lives in
`sofia.sdk.tool_binding`. Its fields and validation are unchanged. The legacy
`sofia.core.cognition.tools` import re-exports the same class object; the actual
cognitive dispatcher and all its independent authority checks remain in Core.
The SDK contract imports no Core or Platform implementation and grants no
capability or owner authority.

Generic Platform tool factories use the SDK binding and existing SDK cognition
payloads directly. Source and installed-wheel probes now block every Core
import while importing catalog, filesystem changes, NET, machine, Fleet,
OPS, DEV and permission inspection surfaces. Factories construct inert tool
descriptions without creating a Core. This expands the former foundation-only
installed isolation list; it does not certify every service lifecycle operation.

Integration and inference package exports load their requested adapters lazily.
Importing a Hyper-V adapter or endpoint configuration no longer imports the
unrelated Discord/Core bridge or the full Ollama cognitive provider. Exported
adapter names still resolve to the same implementation classes. OPS loads its
local workload dispatcher only when an explicit workload catalog is configured.
The Fleet GOALS receipt adapter loads its Core-owned evidence ledger only when
that explicit integration is invoked; its independent evidence checks remain.

Full generic Runtime/individual Core separation is not complete. In particular,
EVOLVE's executor still requires Core Constitution verification, and the GOALS
receipt integration still requires a Core. Neither is silently disabled or
claimed to operate as a Core-free cognitive engine.

Tests cover real SDK/Platform wheel construction and isolation, a clean venv
Core install/uninstall round trip, legacy class identity, independent adapter
loading, tool dispatch authority, inference contracts and host-effect evidence.
No production state, identity, memories, services or writer authority changes.
