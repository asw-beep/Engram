from enum import StrEnum
from uuid import UUID

DEFAULT_TENANT_ID = UUID("00000000-0000-4000-8000-000000000001")
DEFAULT_UPLOAD_SOURCE_ID = UUID("00000000-0000-4000-8000-000000000002")


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    AWAITING_EMBEDDING = "awaiting_embedding"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


# A source may have at most one job in these statuses (partial unique index in 0001_initial).
OPEN_JOB_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING, JobStatus.AWAITING_EMBEDDING)
