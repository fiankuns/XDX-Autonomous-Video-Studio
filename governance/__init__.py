"""XDX Studio v4.0 Governance Package.

Phase 01.6A permission policy + Phase 01.6D trusted human approval & execution guard.
Exports are resolved lazily so low-level modules (``intelligence.state_and_approval``) can import
``governance.trusted_approval`` / ``governance.canonical_manifest`` without a circular import through
``governance.permission_policy`` -> ``adapters`` -> ``intelligence``.
"""

from __future__ import annotations

from typing import Any

__all__ = ["PermissionDeniedError", "PermissionPolicyEngine"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from governance import permission_policy

        return getattr(permission_policy, name)
    raise AttributeError(f"module 'governance' has no attribute {name!r}")
