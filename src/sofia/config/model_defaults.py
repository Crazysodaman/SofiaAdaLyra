"""Editable first-run model defaults.

These values seed owner-editable settings only. No runtime subsystem may
branch on, require, or otherwise depend on these concrete model identities.
"""
DEFAULT_PROVIDER_MODEL = "qwen3:14b"
DEFAULT_ROUTING_PRIMARY_MODEL = "qwen3.5:9b"
DEFAULT_ROUTING_SECONDARY_MODEL = "huihui_ai/qwen3.5-abliterated:4B"
