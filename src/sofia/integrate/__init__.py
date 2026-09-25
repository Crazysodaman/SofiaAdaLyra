"""PKG-INTEGRATE typed, governed adapter registry."""
from .model import AdapterManifest, SideEffectClass, ToolInvocation, ToolReceipt
from .registry import AdapterRegistry, AdapterRegistrationError
from .schema import SchemaValidationError, validate_object
from .policy import InvocationContext, InvocationPolicy
from .receipts import JsonlReceiptLedger, ReceiptRecord
from .governed import GovernedAdapterRegistry, AdapterDisabledError, DuplicateInvocationError
from .activation import AdapterActivationStore
from .capability_adapter import CapabilitySystemAdapter
from .http import JsonHttpClient, JsonHttpError, JsonHttpResponse, UrllibJsonHttpClient
from .adapters import HomeAssistantAdapter, PortainerAdapter, GitHubRepositoryAdapter, JmriAdapter, HyperVAdapter

__all__ = [
    "AdapterManifest","SideEffectClass","ToolInvocation","ToolReceipt",
    "AdapterRegistry","AdapterRegistrationError","SchemaValidationError","validate_object",
    "InvocationContext","InvocationPolicy","JsonlReceiptLedger","ReceiptRecord",
    "GovernedAdapterRegistry","AdapterDisabledError","DuplicateInvocationError",
    "CapabilitySystemAdapter","AdapterActivationStore",
    "JsonHttpClient","JsonHttpError","JsonHttpResponse","UrllibJsonHttpClient",
    "HomeAssistantAdapter","PortainerAdapter","GitHubRepositoryAdapter","JmriAdapter","HyperVAdapter",
]
