"""PKG-SAFE public surface.

Imports are intentionally lazy. SAFE and DEV have governed cross-package
contracts, so eager package-level re-exports can create circular initialization
when callers import a lightweight SAFE submodule such as secret_store.
"""
from __future__ import annotations

from typing import Any

__all__ = [
    "DevApprovalVerifier",
    "ReleaseActivationEvidence",
    "ReleaseActivationGuard",
    "ReleaseSignatureVerifier",
    "ReleaseVerificationError",
]


def __getattr__(name: str) -> Any:
    if name == "DevApprovalVerifier":
        from sofia.safe.dev_approval import DevApprovalVerifier

        return DevApprovalVerifier

    if name in {
        "ReleaseActivationEvidence",
        "ReleaseActivationGuard",
        "ReleaseSignatureVerifier",
        "ReleaseVerificationError",
    }:
        from sofia.safe.release import (
            ReleaseActivationEvidence,
            ReleaseActivationGuard,
            ReleaseSignatureVerifier,
            ReleaseVerificationError,
        )

        return {
            "ReleaseActivationEvidence": ReleaseActivationEvidence,
            "ReleaseActivationGuard": ReleaseActivationGuard,
            "ReleaseSignatureVerifier": ReleaseSignatureVerifier,
            "ReleaseVerificationError": ReleaseVerificationError,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
