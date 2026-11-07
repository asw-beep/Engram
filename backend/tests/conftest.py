import os

os.environ["HF_HUB_OFFLINE"] = "1"

from dataclasses import replace  # noqa: E402
from pathlib import Path  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, delete, func, select, text, update  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import Settings  # noqa: E402
from app.db.base import Base, build_session_factory  # noqa: E402
from app.db.constants import (  # noqa: E402
    DEFAULT_TENANT_ID,
    DEFAULT_UPLOAD_SOURCE_ID,
    OPEN_JOB_STATUSES,
    JobStatus,
)
from app.db.models import (  # noqa: E402
    Chunk,
    Document,
    DocumentVersion,
    IngestionJob,
    Source,
    Tenant,
)
from app.ingestion.connectors.upload import UploadConnector  # noqa: E402
from app.ingestion.jobs import create_job  # noqa: E402
from app.ingestion.pipeline import IngestionDeps, run_ingestion  # noqa: E402
from app.main import create_app  # noqa: E402
from app.storage.files import FileStore  # noqa: E402
from tests.fakes import FailingConnector, FakeEmbedder  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE = "engram_test"
SEEDED_TABLES = {"tenants", "sources"}


@pytest.fixture
def settings():
    return Settings(_env_file=None)


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings))


@pytest.fixture(scope="session")
def test_database_url():
    """Recreate engram_test and migrate it to head, once per test run."""
    base_url = make_url(Settings(_env_file=None).database_url)
    admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{TEST_DATABASE}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{TEST_DATABASE}"'))
    admin.dispose()

    url = base_url.set(database=TEST_DATABASE).render_as_string(hide_password=False)
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    config.attributes["configure_logger"] = False
    command.upgrade(config, "head")
    return url


@pytest.fixture(scope="session")
def migrated_session_factory(test_database_url):
    factory = build_session_factory(test_database_url)
    yield factory
    factory.kw["bind"].dispose()


@pytest.fixture
def session_factory(migrated_session_factory):
    """Empty every table, keeping only the seeded default tenant and upload source."""
    tables = ", ".join(
        table.name for table in Base.metadata.sorted_tables if table.name not in SEEDED_TABLES
    )
    with migrated_session_factory() as session:
        session.execute(text(f"TRUNCATE {tables}"))
        session.execute(delete(Source).where(Source.id != DEFAULT_UPLOAD_SOURCE_ID))
        session.execute(delete(Tenant).where(Tenant.id != DEFAULT_TENANT_ID))
        session.commit()
    return migrated_session_factory


@pytest.fixture
def session(session_factory):
    with session_factory() as session:
        yield session


def _upload_source(session, tenant):
    if tenant is None:
        return session.get(Source, DEFAULT_UPLOAD_SOURCE_ID)
    return session.scalars(select(Source).filter_by(tenant_id=tenant.id, type="upload")).one()


def _save(session, row):
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def make_document(session):
    def make(path="a.md", *, tenant=None, source=None, **fields):
        source = source or _upload_source(session, tenant)
        fields.setdefault("file_type", Path(path).suffix.lstrip(".").lower())
        return _save(
            session, Document(tenant_id=source.tenant_id, source_id=source.id, path=path, **fields)
        )

    return make


@pytest.fixture
def make_version(session, make_document):
    def make(document=None, content_hash=None, **fields):
        document = document or make_document(path=f"{uuid4().hex}.md")
        content_hash = content_hash or uuid4().hex
        fields.setdefault("storage_key", f"{document.tenant_id}/{content_hash}")
        return _save(
            session,
            DocumentVersion(
                tenant_id=document.tenant_id,
                document_id=document.id,
                content_hash=content_hash,
                **fields,
            ),
        )

    return make


@pytest.fixture
def make_chunk(session):
    def make(version, position=0, **fields):
        fields.setdefault("content", f"chunk {position}")
        fields.setdefault("token_count", 2)
        return _save(
            session,
            Chunk(
                tenant_id=version.tenant_id,
                document_version_id=version.id,
                position=position,
                **fields,
            ),
        )

    return make


@pytest.fixture
def make_job(session):
    def make(status="pending", tenant=None, *, source=None, **fields):
        source = source or _upload_source(session, tenant)
        return _save(
            session,
            IngestionJob(tenant_id=source.tenant_id, source_id=source.id, status=status, **fields),
        )

    return make


@pytest.fixture
def store(tmp_path):
    return FileStore(tmp_path / "files")


@pytest.fixture
def deps(session_factory, store, settings):
    return IngestionDeps(
        session_factory=session_factory,
        file_store=store,
        embedder=FakeEmbedder(),
        index=None,
        connector_for=lambda source, job: UploadConnector(store, job.input.get("uploads", [])),
        settings=settings,
    )


def _upload_job(session, input):
    return create_job(session, session.get(Source, DEFAULT_UPLOAD_SOURCE_ID), input)


@pytest.fixture
def ingest(session, store, deps):
    """Save the files, run a job for them on the default upload source, return it refreshed."""

    def run(files, defer_embedding=False):
        uploads = [
            {"path": path, "storage_key": store.put(DEFAULT_TENANT_ID, content)}
            for path, content in files.items()
        ]
        job = _upload_job(session, {"uploads": uploads, "defer_embedding": defer_embedding})
        run_ingestion(job.id, deps)
        session.refresh(job)
        return job

    return run


@pytest.fixture
def ingest_with(session, deps):
    def run(connector):
        job = _upload_job(session, {"uploads": [], "defer_embedding": True})
        run_ingestion(job.id, replace(deps, connector_for=lambda source, job: connector))
        session.refresh(job)
        return job

    return run


@pytest.fixture
def failing_connector():
    return FailingConnector


def _finish_open_jobs(session):
    session.execute(
        update(IngestionJob)
        .where(IngestionJob.status.in_(OPEN_JOB_STATUSES))
        .values(status=JobStatus.SUCCEEDED, finished_at=func.now())
    )


@pytest.fixture
def publish_all(session):
    """Make every document's newest version current, without Qdrant, and finish open jobs."""

    def publish():
        for document in session.scalars(select(Document)):
            document.current_version_id = session.scalars(
                select(DocumentVersion.id)
                .where(DocumentVersion.document_id == document.id)
                .order_by(DocumentVersion.created_at.desc())
            ).first()
        _finish_open_jobs(session)
        session.commit()

    return publish


@pytest.fixture
def finish_job(session):
    """Finish open jobs without publishing anything."""

    def finish():
        _finish_open_jobs(session)
        session.commit()

    return finish
