from __future__ import annotations

from pathlib import Path
import json
import sqlite3

import pytest

from sofia.capability.model import Capability,CapabilityRequest,CapabilityResultKind
from sofia.capability.system import CapabilitySystem
from sofia.composition.root import compose
from sofia.config.defaults import create_default_configuration
from sofia.config.model import ProviderConfiguration,SofiaConfiguration
from sofia.integrations.capabilities import create_configured_integration_tools
from sofia.integrations.github import GitHubAdapter
from sofia.integrations.home_assistant import HomeAssistantAdapter
from sofia.integrations.hyperv import HyperVAdapter
from sofia.integrations.jmri import JmriAdapter
from sofia.integrations.local_maintenance import LocalCommandResult,LocalMaintenanceAdapter
from sofia.integrations.ollama import OllamaAdapter
from sofia.integrations.portainer import PortainerAdapter
from sofia.integrations.sqlite import SQLiteReadAdapter
from sofia.integrations.storage import StorageAdapter
from sofia.knowledge.lifecycle import KnowledgeLifecycle
from sofia.knowledge.persistence import JsonKnowledgeStore
from sofia.knowledge.service import KnowledgeService
from sofia.filesystem.change_capability import FilesystemChangesCapability
from sofia.filesystem.observation import FilesystemObservationStore
from sofia.ops.capability import OpsToolService
from sofia.ops.model import FleetHost,HostLifecycle,HostTelemetry


class FakeHttp:
    def __init__(self,responses=None):
        self.responses=list(responses or [])
        self.calls=[]
    def request(self,method,path,**kwargs):
        self.calls.append((method,path,kwargs))
        return self.responses.pop(0) if self.responses else None


def _configuration(tmp_path:Path,allowed=())->SofiaConfiguration:
    return SofiaConfiguration(
        constitution_path=tmp_path/"constitution.md",
        constitution_hash_path=tmp_path/"constitution.sha256",
        identity_path=tmp_path/"identity.json",
        personality_path=tmp_path/"personality.json",
        avatar_path=tmp_path/"avatar.json",
        state_path=tmp_path/"sofia.db",
        provider=ProviderConfiguration(provider="test",model="test"),
        filesystem_root=tmp_path,
        standing_allowed_capabilities=tuple(allowed),
    )


def test_capability_system_truthfully_lists_registered_capabilities():
    system=CapabilitySystem(lambda request: True)
    system.register(Capability("b.tool","B"),lambda request: None)
    system.register(Capability("a.tool","A"),lambda request: None)
    assert system.capability_names()==("a.tool","b.tool")


def test_default_configuration_exposes_only_safe_core_tool_classes(monkeypatch):
    monkeypatch.delenv("SOFIA_ALLOWED_CAPABILITIES",raising=False)
    cfg=create_default_configuration()
    allowed=set(cfg.standing_allowed_capabilities)
    assert {"tool.catalog","codebase.inspect","filesystem.changes","process.inspect","system.inspect","network.inspect",
            "service.inspect","hardware.inspect","storage.roots","storage.usage","knowledge.search",
            "knowledge.document","dev.status","machine.list","machine.get","machine.discover.local",
            "ops.fleet.list","ops.fleet.get","ops.telemetry.latest","ops.placement.choose",
            "ops.drift.detect","ops.migration.plan","ollama.models","ollama.running","ollama.model.show"} <= allowed
    assert "dev.apply" not in allowed
    assert "home_assistant.service.call" not in allowed
    assert "portainer.container.restart" not in allowed
    assert "hyperv.vm.stop" not in allowed


def test_explicit_environment_capability_grant_is_added(monkeypatch):
    monkeypatch.setenv("SOFIA_ALLOWED_CAPABILITIES","dev.build,dev.apply,github.pull_request.create")
    cfg=create_default_configuration()
    assert "dev.build" in cfg.standing_allowed_capabilities
    assert "dev.apply" in cfg.standing_allowed_capabilities
    assert "github.pull_request.create" in cfg.standing_allowed_capabilities


def test_composition_registers_core_tool_families(tmp_path):
    runtime=compose(_configuration(tmp_path))
    names=set(runtime.capability_system.capability_names())
    assert {"tool.catalog","codebase.inspect","filesystem.inspect","process.inspect","system.inspect",
            "network.inspect","service.inspect","hardware.inspect","knowledge.search",
            "knowledge.document","knowledge.ingest.text","knowledge.ingest.pdf",
            "knowledge.document.write","dev.status","dev.build","dev.apply","dev.rollback",
            "dev.commit","dev.push","machine.list","machine.get","machine.discover.local",
            "machine.refresh.local","ops.fleet.list","ops.fleet.get","ops.telemetry.latest",
            "ops.placement.choose","ops.drift.detect","ops.migration.plan",
            "storage.usage","ollama.models","ollama.running","ollama.model.show"} <= names


def test_ungranted_mutating_dev_tool_is_denied(tmp_path):
    runtime=compose(_configuration(tmp_path,allowed=("dev.status",)))
    cap=runtime.capability_system.resolve("dev.apply")
    result=runtime.capability_system.execute(CapabilityRequest(
        capability=cap,
        parameters={"proposal_id":"p"},
        requested_scope=None,
        rationale="test",
    ))
    assert result.kind is CapabilityResultKind.UNAUTHORIZED


def test_knowledge_ingest_search_and_idempotency(tmp_path):
    source=tmp_path/"manual.txt"
    source.write_text("alpha breaker torque\nbeta wiring note\n",encoding="utf-8")
    store=JsonKnowledgeStore(tmp_path/"knowledge.json")
    lifecycle=KnowledgeLifecycle(tmp_path/"knowledge-lifecycle.json")
    service=KnowledgeService(tmp_path,store,lifecycle)
    first=service.ingest_text("manual.txt",version="v1")
    second=service.ingest_text("manual.txt",version="v1")
    assert first["document_id"]==second["document_id"]
    hits=service.search("breaker torque")
    assert hits
    assert hits[0]["document_id"]==first["document_id"]
    assert "manual.txt" in hits[0]["source_uri"]


def test_knowledge_authoring_is_root_bounded(tmp_path):
    service=KnowledgeService(tmp_path,JsonKnowledgeStore(tmp_path/"k.json"),KnowledgeLifecycle(tmp_path/"l.json"))
    result=service.write_document("docs/test.md","# test")
    assert result["path"]=="docs/test.md"
    assert (tmp_path/"docs"/"test.md").read_text(encoding="utf-8")=="# test"
    with pytest.raises(PermissionError):
        service.write_document("../escape.md","nope")


def test_home_assistant_adapter_is_typed():
    adapter=HomeAssistantAdapter("http://ha.local","token")
    fake=FakeHttp([[{"entity_id":"light.lab"}],{"entity_id":"light.lab","state":"on"},{"ok":True}])
    adapter.http=fake
    assert adapter.states()[0]["entity_id"]=="light.lab"
    assert adapter.state("light.lab")["state"]=="on"
    adapter.call_service("light","turn_off",{"entity_id":"light.lab"})
    assert fake.calls[-1][0:2]==("POST","/api/services/light/turn_off")


def test_portainer_adapter_lists_and_restarts_exact_container():
    adapter=PortainerAdapter("http://portainer.local","key",2)
    fake=FakeHttp([[{"Id":"abc"}],None]); adapter.http=fake
    assert adapter.containers()[0]["Id"]=="abc"
    adapter.restart("abc",timeout_seconds=5)
    assert fake.calls[-1][0:2]==("POST","/api/endpoints/2/docker/containers/abc/restart")
    assert fake.calls[-1][2]["query"]["t"]==5


def test_jmri_adapter_power_and_roster_are_typed():
    adapter=JmriAdapter("http://jmri.local:12080")
    fake=FakeHttp([[{"type":"power"}],[{"type":"roster"}],{"type":"power"}]); adapter.http=fake
    assert adapter.power()[0]["type"]=="power"
    assert adapter.roster()[0]["type"]=="roster"
    adapter.set_power("LocoNet",JmriAdapter.ON,prefix="L")
    assert fake.calls[-1][0]=="POST"
    assert fake.calls[-1][2]["payload"]=={"state":2,"prefix":"L"}


def test_github_adapter_supports_pr_lifecycle_and_decodes_files():
    adapter=GitHubAdapter("owner/repo","token")
    encoded="aGVsbG8="
    fake=FakeHttp([
        {"encoding":"base64","content":encoded},
        [{"number":1}],
        {"number":2},
        {"merged":True},
    ])
    adapter.http=fake
    assert adapter.file("README.md")["decoded_text"]=="hello"
    assert adapter.pull_requests()[0]["number"]==1
    assert adapter.create_pull_request("x","branch","main")["number"]==2
    assert adapter.merge_pull_request(2)["merged"] is True


def test_ollama_adapter_uses_read_only_inspection_endpoints():
    adapter=OllamaAdapter()
    fake=FakeHttp([{"models":[]},{"models":[]},{"details":{}}]); adapter.http=fake
    adapter.models(); adapter.running(); adapter.show("qwen3:14b")
    assert [call[1] for call in fake.calls]==["/api/tags","/api/ps","/api/show"]


def test_hyperv_adapter_uses_typed_vm_names():
    commands=[]
    def runner(command):
        commands.append(command)
        if command.startswith("Get-VM"): return json.dumps({"Name":"Persephone","State":"Running"})
        return ""
    adapter=HyperVAdapter(runner)
    assert adapter.vm("Persephone")["State"]=="Running"
    adapter.start("Persephone")
    assert "Start-VM" in commands[-1]
    with pytest.raises(ValueError):
        adapter.start("bad\nname")


def test_sqlite_adapter_is_read_only(tmp_path):
    db=tmp_path/"db.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE example(id INTEGER PRIMARY KEY,value TEXT)")
        connection.execute("INSERT INTO example(value) VALUES ('x')")
    adapter=SQLiteReadAdapter(db)
    assert "example" in adapter.tables()
    assert adapter.query("SELECT value FROM example")[0]["value"]=="x"
    with pytest.raises(PermissionError):
        adapter.query("DELETE FROM example")


def test_configured_service_catalog_only_appears_when_configured(tmp_path,monkeypatch):
    for key in (
        "SOFIA_HOME_ASSISTANT_URL","SOFIA_HOME_ASSISTANT_TOKEN","SOFIA_PORTAINER_URL",
        "SOFIA_PORTAINER_API_KEY","SOFIA_PORTAINER_ENDPOINT_ID","SOFIA_JMRI_URL",
        "SOFIA_GITHUB_REPOSITORY","SOFIA_GITHUB_TOKEN","SOFIA_DISCORD_OWNER_ID",
        "SOFIA_DISCORD_BOT_ID","SOFIA_DISCORD_DM_CHANNEL_ID",
    ):
        monkeypatch.delenv(key,raising=False)
    names={x.capability.name for x in create_configured_integration_tools(filesystem_root=tmp_path,state_path=tmp_path/"sofia.db")}
    assert "home_assistant.states" not in names
    assert "portainer.containers" not in names
    assert "jmri.power" not in names
    assert "github.repository" not in names
    assert {"storage.usage","ollama.models","ollama.running","ollama.model.show"} <= names


def test_configured_service_catalog_registers_homelab_tools(tmp_path,monkeypatch):
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_URL","http://ha.local")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_TOKEN","token")
    monkeypatch.setenv("SOFIA_PORTAINER_URL","http://portainer.local")
    monkeypatch.setenv("SOFIA_PORTAINER_API_KEY","key")
    monkeypatch.setenv("SOFIA_PORTAINER_ENDPOINT_ID","1")
    monkeypatch.setenv("SOFIA_JMRI_URL","http://jmri.local:12080")
    monkeypatch.setenv("SOFIA_GITHUB_REPOSITORY","owner/repo")
    names={x.capability.name for x in create_configured_integration_tools(filesystem_root=tmp_path,state_path=tmp_path/"sofia.db")}
    assert {"home_assistant.states","home_assistant.service.call","portainer.containers",
            "portainer.container.restart","jmri.power","jmri.power.set","github.repository",
            "github.pull_request.create","github.pull_request.merge"} <= names


def test_tool_catalog_reports_registered_and_standing_authorized(tmp_path):
    runtime=compose(_configuration(tmp_path,allowed=("tool.catalog","dev.status")))
    cap=runtime.capability_system.resolve("tool.catalog")
    result=runtime.capability_system.execute(CapabilityRequest(
        capability=cap,parameters={},requested_scope=None,rationale="inventory tools",
    ))
    assert result.kind is CapabilityResultKind.SUCCESS
    by_name={item["name"]:item for item in result.evidence}
    assert by_name["dev.status"]["standing_authorized"] is True
    assert by_name["dev.apply"]["standing_authorized"] is False
    assert "machine.list" in by_name
    assert "ops.placement.choose" in by_name


def test_ops_placement_tool_uses_durable_fleet_evidence(tmp_path):
    service=OpsToolService(tmp_path/"sofia.db")
    now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    service.registry.register_candidate(FleetHost(
        "venus","windows","x86_64",HostLifecycle.CANDIDATE,True,
        HostTelemetry(now,cpu_percent=25,ram_used_bytes=4,ram_total_bytes=16,storage_free_bytes=100),
    ))
    service.registry.transition("venus",HostLifecycle.ENROLLED)
    decision=service.choose_placement({
        "workload_id":"test","version":"1","supported_platforms":["windows"],
        "supported_architectures":["x86_64"],"min_ram_bytes":1,
    })
    assert decision["host_id"]=="venus"


def test_ops_migration_plan_does_not_execute(tmp_path):
    service=OpsToolService(tmp_path/"sofia.db")
    plan=service.migration_plan({
        "migration_id":"m1",
        "workload":{
            "workload_id":"sofia","version":"1","supported_platforms":["windows"],
            "supported_architectures":["x86_64"],"singleton":True,
        },
        "source_host_id":"venus","target_host_id":"terra",
        "state_mode":"persistent","checkpoint_required":True,
    })
    assert plan["stage"]=="planned"
    assert plan["source_host_id"]=="venus"
    assert plan["target_host_id"]=="terra"
    assert plan["checkpoint_required"] is True


def test_local_maintenance_uses_fixed_argv_and_rejects_shell_input():
    calls=[]
    def runner(argv):
        calls.append(tuple(argv))
        return LocalCommandResult(tuple(argv),0,"","")
    adapter=LocalMaintenanceAdapter(runner)
    adapter.system="Windows"
    adapter.service("Spooler","restart")
    assert calls==[("sc.exe","stop","Spooler"),("sc.exe","start","Spooler")]
    with pytest.raises(ValueError):
        adapter.service("Spooler & whoami","restart")
    with pytest.raises(ValueError):
        adapter.package_update("pkg;rm")


def test_local_reboot_is_fixed_platform_command():
    calls=[]
    def runner(argv):
        calls.append(tuple(argv))
        return LocalCommandResult(tuple(argv),0,"","")
    adapter=LocalMaintenanceAdapter(runner)
    adapter.system="Linux"
    adapter.reboot()
    assert calls==[("systemctl","reboot")]


def test_filesystem_change_tool_ignores_runtime_state_directory(tmp_path):
    state_dir=tmp_path/"state"; state_dir.mkdir()
    state_path=state_dir/"sofia.db"
    store=FilesystemObservationStore(state_path)
    capability=FilesystemChangesCapability(tmp_path,store)
    first=capability.execute(CapabilityRequest(
        capability=capability.capability,parameters={},requested_scope=None,rationale="baseline"))
    assert first["baseline_available"] is False
    (tmp_path/"source.txt").write_text("one",encoding="utf-8")
    second=capability.execute(CapabilityRequest(
        capability=capability.capability,parameters={},requested_scope=None,rationale="delta"))
    assert second["total_changes"]==1
    assert second["new"][0]["path"]=="source.txt"
    third=capability.execute(CapabilityRequest(
        capability=capability.capability,parameters={},requested_scope=None,rationale="stable"))
    assert third["total_changes"]==0
    store.close()


def test_storage_adapter_is_root_confined_and_supports_bounded_management(tmp_path):
    root=tmp_path/"nas"; root.mkdir()
    storage=StorageAdapter((root,))
    assert storage.roots_info()[0]["index"]==0
    storage.mkdir(0,"docs")
    storage.write_text(0,"docs/a.txt","hello")
    assert storage.read_text(0,"docs/a.txt")=="hello"
    storage.copy(0,"docs/a.txt","docs/b.txt")
    storage.move(0,"docs/b.txt","docs/c.txt")
    assert {x["name"] for x in storage.list(0,"docs")}=={"a.txt","c.txt"}
    storage.delete(0,"docs/c.txt")
    with pytest.raises(PermissionError):
        storage.write_text(0,"../escape.txt","nope")


def test_sqlite_management_is_specific_not_arbitrary_write(tmp_path):
    db=tmp_path/"state.db"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE example(value TEXT)")
        connection.execute("INSERT INTO example VALUES ('x')")
    adapter=SQLiteReadAdapter(db)
    assert adapter.integrity_check()==("ok",)
    backup=adapter.backup()
    assert Path(backup["destination"]).exists()
    checkpoint=adapter.wal_checkpoint("PASSIVE")
    assert len(checkpoint)==3
    assert adapter.vacuum()["vacuumed"] is True
    with pytest.raises(PermissionError):
        adapter.query("UPDATE example SET value='y'")


def test_notification_tool_is_registered_only_when_ha_notify_service_configured(tmp_path,monkeypatch):
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_URL","http://ha.local")
    monkeypatch.setenv("SOFIA_HOME_ASSISTANT_TOKEN","token")
    monkeypatch.setenv("SOFIA_NOTIFICATION_HA_SERVICE","mobile_app_sparks")
    names={x.capability.name for x in create_configured_integration_tools(
        filesystem_root=tmp_path,state_path=tmp_path/"sofia.db")}
    assert "notification.send" in names


def test_knowledge_same_bytes_different_versions_keep_distinct_provenance(tmp_path):
    source=tmp_path/"manual.txt"; source.write_text("same content",encoding="utf-8")
    service=KnowledgeService(tmp_path,JsonKnowledgeStore(tmp_path/"k.json"),KnowledgeLifecycle(tmp_path/"l.json"))
    first=service.ingest_text("manual.txt",version="rev-a")
    second=service.ingest_text("manual.txt",version="rev-b")
    assert first["document_id"]!=second["document_id"]


def test_knowledge_pdf_identity_includes_declared_version(tmp_path):
    from pypdf import PdfWriter
    pdf=tmp_path/"manual.pdf"
    writer=PdfWriter()
    writer.add_blank_page(width=72,height=72)
    with pdf.open("wb") as handle:
        writer.write(handle)
    service=KnowledgeService(
        tmp_path,
        JsonKnowledgeStore(tmp_path/"pdf-knowledge.json"),
        KnowledgeLifecycle(tmp_path/"pdf-lifecycle.json"),
    )
    first=service.ingest_pdf("manual.pdf",version="rev-a")
    second=service.ingest_pdf("manual.pdf",version="rev-b")
    assert first["document_id"]!=second["document_id"]


def test_storage_returns_canonical_forward_slash_relative_paths(tmp_path):
    root=tmp_path/"nas"; root.mkdir()
    storage=StorageAdapter((root,))
    storage.mkdir(0,"docs")
    written=storage.write_text(0,"docs/test.txt","hello")
    assert written["path"]=="docs/test.txt"
    listed=storage.list(0,"docs")
    assert listed[0]["path"]=="docs/test.txt"
