"""Tenants shared by retrieval and isolation tests. The `two_tenants` fixture creates A and B."""

from uuid import UUID

from app.db.constants import DEFAULT_TENANT_ID
from app.types import AccessScope

TENANT_A = UUID("aaaaaaaa-0000-4000-8000-00000000000a")
TENANT_B = UUID("bbbbbbbb-0000-4000-8000-00000000000b")
DEFAULT_SCOPE = AccessScope(DEFAULT_TENANT_ID, ("tenant",))
