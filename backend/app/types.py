"""Types shared across modules that must not import each other."""

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class AccessScope:
    """Who is asking: their tenant and the principals they hold."""

    tenant_id: UUID
    principals: tuple[str, ...]
