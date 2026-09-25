"""Governed adapter registry for production paths."""
from __future__ import annotations
from .activation import AdapterActivationStore
from .registry import AdapterRegistry,Adapter
from .model import ToolInvocation,ToolReceipt
from .policy import InvocationContext,InvocationPolicy
from .receipts import JsonlReceiptLedger

class AdapterDisabledError(PermissionError): pass
class DuplicateInvocationError(PermissionError): pass

class GovernedAdapterRegistry:
    def __init__(self,ledger:JsonlReceiptLedger,policy:InvocationPolicy|None=None,
                 activations:AdapterActivationStore|None=None)->None:
        self.registry=AdapterRegistry(); self.ledger=ledger; self.policy=policy or InvocationPolicy()
        self.activations=activations or AdapterActivationStore()
    def register(self,adapter:Adapter,*,enabled:bool=False)->None:
        self.registry.register(adapter)
        if enabled: self.activations.enable(adapter.manifest.tool_id,adapter.manifest.version)
    def enable(self,tool_id:str,version:str)->None:
        manifest=self.registry.manifest(tool_id)
        if manifest is None: raise KeyError(f"unknown tool: {tool_id}")
        if manifest.version!=version: raise ValueError("tool version does not match registered adapter")
        self.activations.enable(tool_id,version)
    def disable(self,tool_id:str)->None: self.activations.disable(tool_id)
    def invoke(self,request:ToolInvocation,context:InvocationContext)->ToolReceipt:
        manifest=self.registry.manifest(request.tool_id)
        if manifest is None: raise KeyError(f"unknown tool: {request.tool_id}")
        if self.activations.version(request.tool_id)!=manifest.version:
            raise AdapterDisabledError("adapter version is not enabled")
        if self.ledger.get(request.invocation_id) is not None:
            raise DuplicateInvocationError("invocation_id already has a durable receipt")
        if not request.authorized:
            raise PermissionError("tool invocation lacks independent authorization")
        self.policy.require(manifest,context)
        receipt=self.registry.invoke(request)
        self.ledger.append(receipt)
        return receipt
