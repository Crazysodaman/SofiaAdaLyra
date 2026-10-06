"""Matrix-owned capability/tool relevance planning.

The planner selects host capability names that are relevant to one turn.
It does not grant capability authority or execution approval.
"""
from __future__ import annotations

import re

from sofia.safe.permissions import PermissionLevel, capability_permission_policy

from .model import (
    AuthorityDecision,
    AuthorityPlan,
    MatrixIntent,
    ToolExposurePlan,
    TurnEnvelope,
    TurnMatrix,
)

_PROCESS = re.compile(r"\b(?:process(?:es)?|running\s+(?:apps?|programs?))\b", re.IGNORECASE)
_RUNNING_APP = re.compile(r"\b(?:is|are)\s+[A-Za-z0-9_.-]+\s+running\b|\bwhat(?:'|’)s\s+running\b", re.IGNORECASE)
_HARDWARE = re.compile(r"\b(?:cpu|gpu|ram|memory\s+usage|hardware|sensors?)\b", re.IGNORECASE)
_NETWORK = re.compile(r"\b(?:network|dns|routes?|interfaces?|packet\s+loss|latency)\b", re.IGNORECASE)
_NETWORK_HOSTS = re.compile(r"\b(?:computers?|devices?|hosts?|machines?)\b", re.IGNORECASE)
_OTHER_COMPUTERS = re.compile(
    r"\b(?:other|known|available)\s+(?:computers?|machines?|hosts?|nodes?|devices?)\b"
    r"|\b(?:see|know\s+about|access)\s+(?:any\s+)?(?:other\s+)?"
    r"(?:computers?|machines?|hosts?|nodes?|devices?)\b",
    re.IGNORECASE,
)
_SERVICE = re.compile(r"\bservices?\b", re.IGNORECASE)
_SYSTEM = re.compile(r"\b(?:system|computer|local\s+host|host\s+status|uptime)\b", re.IGNORECASE)
_MACHINE = re.compile(r"\b(?:machine|machines|inventory)\b", re.IGNORECASE)
_FLEET = re.compile(r"\b(?:fleet|telemetry|placement|drift|migration|remote)\b", re.IGNORECASE)
_FILESYSTEM = re.compile(r"\b(?:file|folder|directory|filesystem)\b", re.IGNORECASE)
_CODE = re.compile(r"\b(?:code|codebase|source|repository|repo|git\b|github)\b", re.IGNORECASE)
_SELF_IMPROVE = re.compile(
    r"\b(?:self[- ]?improv(?:e|ement)|improve\s+yourself|fix\s+yourself|work\s+on\s+yourself|improve\s+your\s+code|fix\s+your\s+code|optimi[sz]e\s+your\s+code)\b",
    re.IGNORECASE,
)
_EVOLVE = re.compile(
    r"\b(?:evolv(?:e|ing|ution)|evolution\s+proposals?|"
    r"improvement\s+proposals?|change\s+your\s+(?:preferences?|configuration|constitution|identity))\b",
    re.IGNORECASE,
)
_GITHUB = re.compile(r"\b(?:github|issues?|pull\s+requests?|\bpr\b)\b", re.IGNORECASE)
_KNOWLEDGE = re.compile(r"\b(?:knowledge|manual|documentation|document|pdf)\b", re.IGNORECASE)
_HOME_ASSISTANT = re.compile(r"\bhome\s+assistant\b", re.IGNORECASE)
_PORTAINER = re.compile(r"\b(?:portainer|docker|containers?)\b", re.IGNORECASE)
_JMRI = re.compile(r"\b(?:jmri|locomotive|roster|track\s+power)\b", re.IGNORECASE)
_DISCORD = re.compile(r"\bdiscord\b", re.IGNORECASE)
_OLLAMA = re.compile(r"\bollama\b", re.IGNORECASE)
_VM = re.compile(r"\b(?:hyper[- ]?v|virtual\s+machines?|\bvms?\b)\b", re.IGNORECASE)
_STORAGE = re.compile(r"\b(?:storage|nas|disk\s+usage|shares?)\b", re.IGNORECASE)
_SQLITE = re.compile(r"\b(?:sqlite|database|\bdb\b)\b", re.IGNORECASE)
_NOTIFICATION = re.compile(r"\b(?:notification|notify)\b", re.IGNORECASE)
_RELEASE = re.compile(r"\b(?:release|deployment|rollout)\b", re.IGNORECASE)
_TOOL_CATALOG = re.compile(r"\b(?:tools?|capabilities|what\s+can\s+you\s+do)\b", re.IGNORECASE)
_PERMISSIONS = re.compile(
    r"\b(?:permissions?|authority|standing\s+grants?|what\s+(?:are\s+you|you(?:'|’)re)\s+allowed\s+to\s+do)\b",
    re.IGNORECASE,
)
_WEB_SEARCH = re.compile(
    r"\b(?:search|browse|look\s+up|find)\b.{0,48}\b(?:web|internet|online)\b"
    r"|\b(?:web|internet|online)\b.{0,48}\b(?:search|research|results?|answers?|ideas?)\b",
    re.IGNORECASE | re.DOTALL,
)
_WEB_URL = re.compile(r"https://[^\s<>]+", re.IGNORECASE)

_START = re.compile(r"\bstart\b", re.IGNORECASE)
_STOP = re.compile(r"\bstop\b", re.IGNORECASE)
_RESTART = re.compile(r"\brestart\b", re.IGNORECASE)
_REBOOT = re.compile(r"\breboot\b", re.IGNORECASE)
_UPDATE = re.compile(r"\b(?:update|upgrade)\b", re.IGNORECASE)
_REFRESH = re.compile(r"\brefresh\b", re.IGNORECASE)
_DISCOVER = re.compile(r"\b(?:discover|scan|find|look\s+for|search\s+for)\b", re.IGNORECASE)
_FLEET_ENROLL = re.compile(
    r"\b(?:add|enroll|join|trust)\b.*\bfleet\b|\bfleet\b.*\b(?:add|enroll|join|trust)\b",
    re.IGNORECASE,
)
_CREATE = re.compile(r"\bcreate\b", re.IGNORECASE)
_MERGE = re.compile(r"\bmerge\b", re.IGNORECASE)
_WRITE = re.compile(r"\b(?:write|edit|change)\b", re.IGNORECASE)
_DELETE = re.compile(r"\b(?:delete|remove)\b", re.IGNORECASE)
_PAUSE = re.compile(r"\bpause\b", re.IGNORECASE)
_RESUME = re.compile(r"\bresume\b", re.IGNORECASE)
_REVOKE = re.compile(r"\brevoke\b", re.IGNORECASE)
_BACKUP = re.compile(r"\bbackup\b", re.IGNORECASE)
_VACUUM = re.compile(r"\bvacuum\b", re.IGNORECASE)
_CHECKPOINT = re.compile(r"\bcheckpoint\b", re.IGNORECASE)
_POWER_SET = re.compile(r"\b(?:set|turn)\b.*\bpower\b|\bpower\b.*\b(?:on|off)\b", re.IGNORECASE)
_MODEL_LOAD = re.compile(r"\bload\b", re.IGNORECASE)
_MODEL_UNLOAD = re.compile(r"\bunload\b", re.IGNORECASE)
_MODEL_INSTALL = re.compile(r"\b(?:install|pull)\b", re.IGNORECASE)


def _add(target: list[str], *values: str) -> None:
    for value in values:
        if value not in target:
            target.append(value)


class MatrixToolExposurePlanner:
    """Select a bounded capability allowlist for the current turn."""

    def plan(
        self,
        envelope: TurnEnvelope,
        turn: TurnMatrix,
        authority: AuthorityPlan,
    ) -> ToolExposurePlan:
        if not isinstance(envelope, TurnEnvelope):
            raise TypeError("envelope must be TurnEnvelope")
        if not isinstance(turn, TurnMatrix):
            raise TypeError("turn must be TurnMatrix")
        if not isinstance(authority, AuthorityPlan):
            raise TypeError("authority must be AuthorityPlan")

        text = envelope.content.strip()
        capabilities: list[str] = []

        if _RUNNING_APP.search(text) or _PROCESS.search(text):
            _add(capabilities, "process.inspect")
        if _HARDWARE.search(text):
            _add(
                capabilities,
                "hardware.inspect",
                "machine.list",
                "machine.get",
                "ops.fleet.list",
                "ops.fleet.get",
                "remote.nodes",
                "remote.hardware.inspect",
            )
        if _NETWORK.search(text):
            _add(capabilities, "network.inspect")
            if _DISCOVER.search(text) or _NETWORK_HOSTS.search(text):
                _add(capabilities, "network.discover")
        if _SERVICE.search(text):
            _add(capabilities, "service.inspect")
        if _SYSTEM.search(text):
            _add(capabilities, "system.inspect")
        if _MACHINE.search(text):
            _add(capabilities, "machine.list", "machine.get", "machine.discover.local")
        if _OTHER_COMPUTERS.search(text):
            _add(
                capabilities,
                "machine.list",
                "machine.get",
                "ops.fleet.list",
                "ops.fleet.get",
                "remote.nodes",
            )
            if _DISCOVER.search(text) and _NETWORK.search(text):
                _add(capabilities, "ops.fleet.discover")
        if _FLEET.search(text):
            _add(capabilities, "ops.fleet.list", "ops.fleet.get", "ops.telemetry.latest", "remote.nodes")
            if _FLEET_ENROLL.search(text):
                _add(capabilities, "ops.fleet.enrollment_evidence", "fleet.enroll")
            if _DISCOVER.search(text):
                _add(capabilities, "ops.fleet.discover")
            if re.search(r"\bplacement\b", text, re.IGNORECASE):
                _add(capabilities, "ops.placement.choose")
            if re.search(r"\bdrift\b", text, re.IGNORECASE):
                _add(capabilities, "ops.drift.detect")
                if re.search(r"\b(?:propose|repair|fix)\b", text, re.IGNORECASE):
                    _add(capabilities, "ops.drift.propose")
            if re.search(r"\breconcil(?:e|iation)\b", text, re.IGNORECASE):
                if re.search(r"\b(?:active|current|list|show)\b", text, re.IGNORECASE):
                    _add(capabilities, "ops.reconcile.active")
                else:
                    _add(capabilities, "ops.reconcile.preview")
            if re.search(r"\bmigration\b", text, re.IGNORECASE):
                _add(capabilities, "ops.migration.plan")
                if re.search(r"\b(?:receipt|status|result)\b", text, re.IGNORECASE):
                    _add(capabilities, "ops.migration.receipt")
            if re.search(r"\bmaintenance\b", text, re.IGNORECASE) and re.search(
                r"\b(?:receipt|result)\b", text, re.IGNORECASE
            ):
                _add(capabilities, "ops.maintenance.receipt")
        if _FILESYSTEM.search(text):
            _add(capabilities, "filesystem.inspect")
            if re.search(r"\bchanges?\b", text, re.IGNORECASE):
                _add(capabilities, "filesystem.changes")
        if _CODE.search(text) or _SELF_IMPROVE.search(text):
            _add(
                capabilities,
                "filesystem.inspect",
                "codebase.inspect",
                "dev.status",
                "dev.candidates.list",
                "dev.candidate.get",
            )
            if _SELF_IMPROVE.search(text):
                _add(capabilities, "dev.build")
        if _EVOLVE.search(text) or _SELF_IMPROVE.search(text):
            _add(
                capabilities,
                "evolve.evidence.list",
                "evolve.proposals.list",
                "evolve.proposal.get",
                "evolve.proposal.revision.create",
                "evolve.proposal.amendment.create",
                "evolve.proposal.code.create",
            )
            if _SELF_IMPROVE.search(text):
                _add(capabilities, "evolve.code.candidate.build")
        if _GITHUB.search(text):
            _add(capabilities, "github.repository", "github.issues", "github.file", "github.pull_requests")
        if _KNOWLEDGE.search(text):
            _add(capabilities, "knowledge.search", "knowledge.document")
        if _HOME_ASSISTANT.search(text):
            _add(capabilities, "home_assistant.services", "home_assistant.states", "home_assistant.state")
        if _PORTAINER.search(text):
            _add(
                capabilities,
                "portainer.endpoints",
                "portainer.containers",
                "portainer.container",
                "portainer.container.stats",
                "portainer.container.logs",
                "portainer.info",
                "portainer.summary",
                "portainer.images",
                "portainer.volumes",
                "portainer.networks",
                "portainer.stacks",
                "ops.fleet.list",
                "ops.fleet.get",
                "remote.nodes",
                "remote.container.list",
                "remote.container.get",
                "remote.container.stats",
                "remote.container.info",
                "remote.container.summary",
                "remote.container.images",
                "remote.container.volumes",
                "remote.container.networks",
                "remote.container.stacks",
            )
        if _JMRI.search(text):
            _add(capabilities, "jmri.power", "jmri.roster", "jmri.object")
        if _DISCORD.search(text):
            _add(capabilities, "discord.status")
        if _OLLAMA.search(text):
            _add(capabilities, "ollama.models", "ollama.running", "ollama.model.show")
        if _VM.search(text):
            _add(capabilities, "hyperv.vms", "hyperv.vm", "remote.vm.list", "remote.vm.get")
        if _STORAGE.search(text):
            _add(capabilities, "storage.roots", "storage.usage", "storage.list", "storage.read_text")
        if _SQLITE.search(text):
            _add(capabilities, "sqlite.state.tables", "sqlite.state.query", "sqlite.state.integrity")
        if _RELEASE.search(text) and re.search(
            r"\b(?:remote|fleet|node|host)\b", text, re.IGNORECASE
        ):
            _add(capabilities, "remote.release.current")
        if _TOOL_CATALOG.search(text):
            _add(capabilities, "tool.catalog")
        if _PERMISSIONS.search(text):
            _add(capabilities, "permissions.inspect")
        if _WEB_SEARCH.search(text):
            _add(capabilities, "web.search")
        if _WEB_URL.search(text) and re.search(
            r"\b(?:open|fetch|read|inspect|summarize|check|browse)\b",
            text,
            re.IGNORECASE,
        ):
            _add(capabilities, "web.fetch")

        remote = bool(re.search(r"\bremote\b", text, re.IGNORECASE))
        if remote:
            if _PROCESS.search(text) or _RUNNING_APP.search(text):
                _add(capabilities, "remote.process.inspect")
            if _SYSTEM.search(text):
                _add(capabilities, "remote.system.inspect")
            if _NETWORK.search(text):
                _add(capabilities, "remote.network.inspect")
            if _SERVICE.search(text):
                _add(capabilities, "remote.service.inspect")
            if _HARDWARE.search(text):
                _add(capabilities, "remote.hardware.inspect")
            if _PORTAINER.search(text):
                _add(
                    capabilities,
                    "remote.container.list",
                    "remote.container.get",
                    "remote.container.stats",
                    "remote.container.logs",
                    "remote.container.info",
                    "remote.container.summary",
                    "remote.container.images",
                    "remote.container.volumes",
                    "remote.container.networks",
                    "remote.container.stacks",
                )
            if _OLLAMA.search(text):
                _add(capabilities, "remote.ollama.inference_policy", "remote.ollama.models", "remote.ollama.running", "remote.ollama.show")

        if turn.intent is MatrixIntent.ACTION_REQUEST:
            if _SERVICE.search(text):
                if _RESTART.search(text):
                    _add(capabilities, "local.service.restart", "remote.service.restart")
                elif _START.search(text):
                    _add(capabilities, "local.service.start", "remote.service.start")
                elif _STOP.search(text):
                    _add(capabilities, "local.service.stop", "remote.service.stop")
            if _REBOOT.search(text):
                _add(capabilities, "local.host.reboot", "remote.host.reboot")
            if _UPDATE.search(text) and re.search(r"\bpackage\b", text, re.IGNORECASE):
                _add(capabilities, "local.package.update", "remote.package.update")
            if _VM.search(text):
                if _START.search(text):
                    _add(capabilities, "hyperv.vm.start", "remote.vm.start")
                if _STOP.search(text):
                    _add(capabilities, "hyperv.vm.stop", "remote.vm.stop")
            if _PORTAINER.search(text) and _RESTART.search(text):
                _add(capabilities, "portainer.container.restart", "remote.container.restart")
            if _HOME_ASSISTANT.search(text):
                _add(capabilities, "home_assistant.service.call")
            if _JMRI.search(text) and _POWER_SET.search(text):
                _add(capabilities, "jmri.power.set")
            if _DISCORD.search(text):
                if _PAUSE.search(text):
                    _add(capabilities, "discord.pause")
                if _RESUME.search(text):
                    _add(capabilities, "discord.resume")
                if _REVOKE.search(text):
                    _add(capabilities, "discord.revoke")
            if _NOTIFICATION.search(text) and re.search(
                r"\b(?:send|push|deliver|notify)\b", text, re.IGNORECASE
            ):
                _add(capabilities, "notification.send")
            if _GITHUB.search(text):
                if _CREATE.search(text) and re.search(r"\bissue\b", text, re.IGNORECASE):
                    _add(capabilities, "github.issue.create")
                if _CREATE.search(text) and re.search(r"\b(?:pull\s+request|\bpr\b)\b", text, re.IGNORECASE):
                    _add(capabilities, "github.pull_request.create")
                if _MERGE.search(text):
                    _add(capabilities, "github.pull_request.merge")
            if _MACHINE.search(text) and _REFRESH.search(text):
                _add(capabilities, "machine.refresh.local")
            if _STORAGE.search(text):
                if _WRITE.search(text):
                    _add(capabilities, "storage.write_text", "storage.mkdir", "storage.copy", "storage.move")
                if _DELETE.search(text):
                    _add(capabilities, "storage.delete")
            if _SQLITE.search(text):
                if _BACKUP.search(text):
                    _add(capabilities, "sqlite.state.backup")
                if _CHECKPOINT.search(text):
                    _add(capabilities, "sqlite.state.wal_checkpoint")
                if _VACUUM.search(text):
                    _add(capabilities, "sqlite.state.vacuum")
            if _OLLAMA.search(text):
                if _MODEL_INSTALL.search(text):
                    _add(capabilities, "remote.ollama.pull")
                if _MODEL_LOAD.search(text):
                    _add(capabilities, "remote.ollama.load")
                if _MODEL_UNLOAD.search(text):
                    _add(capabilities, "remote.ollama.unload")
            if _CODE.search(text) or _SELF_IMPROVE.search(text):
                if (
                    _SELF_IMPROVE.search(text)
                    or re.search(r"\bbuild\b", text, re.IGNORECASE)
                    or _WRITE.search(text)
                ):
                    _add(capabilities, "dev.build")
                if re.search(r"\bapply\b", text, re.IGNORECASE):
                    _add(capabilities, "dev.apply")
                if re.search(r"\brollback\b", text, re.IGNORECASE):
                    _add(capabilities, "dev.rollback")
                if re.search(r"\bcommit\b", text, re.IGNORECASE):
                    _add(capabilities, "dev.commit")
                if re.search(r"\bpush\b", text, re.IGNORECASE):
                    _add(capabilities, "dev.push")
            if _EVOLVE.search(text):
                if re.search(r"\bapply\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.apply")
                if re.search(r"\brollback\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.rollback")
            if _FLEET.search(text) and re.search(
                r"\bmigration\b", text, re.IGNORECASE
            ):
                if re.search(
                    r"\b(?:execute|migrate|move|run|start)\b",
                    text,
                    re.IGNORECASE,
                ):
                    _add(capabilities, "ops.migration.execute")
            if _EVOLVE.search(text) or _SELF_IMPROVE.search(text):
                if re.search(r"\bbuild\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.code.candidate.build")
                if re.search(r"\b(?:verify|test)\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.code.candidate.verify")
                if re.search(r"\b(?:release|rollout|activate)\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.code.release.accept")
                if re.search(r"\bapply\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.code.candidate.apply")
                if re.search(r"\bcommit\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.code.candidate.commit")
                if re.search(r"\brollback\b", text, re.IGNORECASE):
                    _add(capabilities, "evolve.code.candidate.rollback")
            if _KNOWLEDGE.search(text):
                if re.search(r"\bingest\b", text, re.IGNORECASE):
                    _add(capabilities, "knowledge.ingest.text", "knowledge.ingest.pdf")
                if _WRITE.search(text):
                    _add(capabilities, "knowledge.document.write")

        if (
            turn.intent is MatrixIntent.ACTION_REQUEST
            and authority.decision is not AuthorityDecision.ALLOWED
        ):
            capabilities = [
                capability
                for capability in capabilities
                if (
                    capability_permission_policy(capability).level
                    in {
                        PermissionLevel.OBSERVE_READ,
                        PermissionLevel.SAFE_AUTONOMOUS,
                    }
                    or (
                        capability_permission_policy(capability).level
                        in {
                            PermissionLevel.REVERSIBLE_SCOPED,
                            PermissionLevel.PROTECTED,
                        }
                        and capability in authority.allowed_capabilities
                    )
                )
            ]

        if not capabilities:
            return ToolExposurePlan(
                (),
                (
                    "turn has no matrix-relevant capability that is autonomous "
                    "under the central permission policy"
                ),
            )
        return ToolExposurePlan(
            tuple(capabilities),
            (
                "matrix relevance selected a bounded capability allowlist; "
                "Level-1/2 capabilities remain available without action "
                "approval while host authority still governs Level-3/4 execution"
            ),
        )
