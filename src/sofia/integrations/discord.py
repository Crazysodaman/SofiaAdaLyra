"""Local Discord control-state adapter. No Discord token or network I/O."""
from __future__ import annotations
from pathlib import Path
from sofia.discord.binding import BindingState,DiscordBindingStore
from sofia.discord.delivery import DiscordDeliveryStore
from sofia.discord.provisioning import DiscordIdentity
from sofia.discord.store import DiscordInboxStore

class DiscordOperatorAdapter:
    def __init__(self,state_path:Path,identity:DiscordIdentity)->None:
        self.state_path=state_path; self.identity=identity
    def status(self)->dict:
        bindings=DiscordBindingStore(self.state_path)
        binding=bindings.get(bot_user_id=self.identity.bot_user_id,channel_id=self.identity.dm_channel_id)
        if binding is None: return {"state":"unbound"}
        if binding.owner_user_id!=self.identity.owner_user_id: raise PermissionError("Discord durable binding belongs to another owner")
        inbox=DiscordInboxStore(self.state_path); deliveries=DiscordDeliveryStore(self.state_path)
        pending=inbox.list_outbox(bot_user_id=self.identity.bot_user_id,channel_id=self.identity.dm_channel_id,states=("prepared",))
        return {"state":binding.state.value,"session_id":binding.session_id,"generation":binding.generation,
            "pending_outbox":len(pending),"unknown_generation_outcomes":inbox.count_outcome_unknown(),
            "unknown_delivery_outcomes":deliveries.count_outcome_unknown()}
    def control(self,action:str)->dict:
        if action not in ("pause","resume","revoke"): raise ValueError("Discord action must be pause, resume, or revoke")
        bindings=DiscordBindingStore(self.state_path)
        binding=bindings.get(bot_user_id=self.identity.bot_user_id,channel_id=self.identity.dm_channel_id)
        if binding is None: raise RuntimeError("Discord channel is not bound")
        if binding.owner_user_id!=self.identity.owner_user_id: raise PermissionError("Discord durable binding belongs to another owner")
        kwargs={"bot_user_id":self.identity.bot_user_id,"channel_id":self.identity.dm_channel_id}
        if action=="pause": bindings.pause(**kwargs)
        elif action=="resume": bindings.resume(**kwargs)
        else: bindings.revoke(**kwargs)
        return self.status()
