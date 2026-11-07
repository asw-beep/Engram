"""Original files on disk, stored once per tenant and content hash."""

import hashlib
import re
from pathlib import Path
from uuid import UUID, uuid4

_DIGEST = re.compile(r"[0-9a-f]{64}")


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


class FileStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def put(self, tenant_id: UUID, content: bytes) -> str:
        key = f"{tenant_id}/{content_hash(content)}"
        path = self._path(key)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            partial = path.with_name(f"{path.name}.{uuid4().hex}.partial")
            partial.write_bytes(content)
            partial.replace(path)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def _path(self, key: str) -> Path:
        """Accept only `<tenant uuid>/<sha256>`, so a key can never leave the store."""
        tenant, _, digest = key.partition("/")
        try:
            tenant_id = UUID(tenant)
        except ValueError:
            raise ValueError(f"invalid storage key {key!r}") from None
        if str(tenant_id) != tenant or not _DIGEST.fullmatch(digest):
            raise ValueError(f"invalid storage key {key!r}")
        return self.root / tenant / digest
