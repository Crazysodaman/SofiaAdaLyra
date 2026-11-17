"""Client-facing CLI/TUI/desktop/Android chat projections for Aegis social."""
from sofia.platform.chat_clients.accessibility import (
    KeyboardCommand,
    accessibility_summary,
    focus_order,
    keyboard_commands,
)
from sofia.platform.chat_clients.android import (
    AndroidCapabilities,
    AndroidRemoteChatSession,
    MobileDeliveredReceipt,
)
from sofia.platform.chat_clients.contracts import (
    ChatEvent,
    ChatMessage,
    ChatOffline,
    ChatPermissionDenied,
    ChatRoom,
    ConnectionState,
    CoreIdentity,
    MembershipStatus,
    MessageOrigin,
    MessagePage,
    RoomKind,
    RoomMembership,
    SendReceipt,
    SendStatus,
)
from sofia.platform.chat_clients.controller import (
    ChannelView,
    ChatClientController,
    ClientIdentityResult,
    ClientNotice,
    ClientSnapshot,
    MemberView,
    NotificationMode,
    PendingSend,
    PendingSendStatus,
    RenderedMessage,
)
from sofia.platform.chat_clients.desktop import (
    DesktopClientCapabilities,
    RemoteDesktopChatClient,
)
from sofia.platform.chat_clients.drafts import (
    ClientDraft,
    ClientDraftStore,
    MemoryDraftPersistence,
)
from sofia.platform.chat_clients.render import (
    render_chat_screen,
    render_messages,
    render_sidebar,
    shared_theme_tokens,
)
from sofia.platform.chat_clients.stage6_simulation import (
    EvidenceCategory,
    ScenarioEvidence,
    Stage6Report,
    Stage6ScenarioRunner,
    SyntheticStage6World,
    run_stage6_deterministic_suite,
)
from sofia.platform.chat_clients.voice import (
    AudioEvidenceKind,
    AudioTestEvidence,
    SimultaneousCoreVoiceSeam,
    VoiceSeamReport,
)

__all__ = [
    "KeyboardCommand", "accessibility_summary", "focus_order",
    "keyboard_commands", "AndroidCapabilities", "AndroidRemoteChatSession",
    "MobileDeliveredReceipt", "ChatEvent", "ChatMessage", "ChatOffline",
    "ChatPermissionDenied", "ChatRoom", "ConnectionState", "CoreIdentity",
    "MembershipStatus", "MessageOrigin", "MessagePage", "RoomKind",
    "RoomMembership", "SendReceipt", "SendStatus", "ChannelView",
    "ChatClientController", "ClientIdentityResult", "ClientNotice",
    "ClientSnapshot", "MemberView", "NotificationMode", "PendingSend",
    "PendingSendStatus", "RenderedMessage", "DesktopClientCapabilities",
    "RemoteDesktopChatClient", "ClientDraft", "ClientDraftStore",
    "MemoryDraftPersistence", "render_chat_screen", "render_messages",
    "render_sidebar", "shared_theme_tokens", "EvidenceCategory",
    "ScenarioEvidence", "Stage6Report", "Stage6ScenarioRunner",
    "SyntheticStage6World", "run_stage6_deterministic_suite",
    "AudioEvidenceKind", "AudioTestEvidence", "SimultaneousCoreVoiceSeam",
    "VoiceSeamReport",
]
