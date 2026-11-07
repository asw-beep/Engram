import os

os.environ["HF_HUB_OFFLINE"] = "1"

from contextlib import contextmanager  # noqa: E402
from dataclasses import fields, replace  # noqa: E402
from pathlib import Path  # noqa: E402
from uuid import uuid4  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from qdrant_client import QdrantClient, models  # noqa: E402
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
from app.db.vector_index import IndexedPoint, VectorIndex  # noqa: E402
from app.ingestion.connectors.upload import UploadConnector  # noqa: E402
from app.ingestion.jobs import create_job, retry_job  # noqa: E402
from app.ingestion.pipeline import IngestionDeps, run_ingestion  # noqa: E402
from app.main import create_app  # noqa: E402
from app.retrieval.dense import DenseRetriever  # noqa: E402
from app.services import Services  # noqa: E402
from app.storage.files import FileStore  # noqa: E402
from tests.fakes import FailingConnector, FakeEmbedder, FakeLLM  # noqa: E402
from tests.tenants import TENANT_A, TENANT_B  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_DATABASE = "engram_test"
SEEDED_TABLES = {"tenants", "sources"}


@pytest.fixture
def settings():
    # FakeEmbedder's bag-of-words scores run lower than BGE-M3's, so the tests keep their own
    # evidence cutoff instead of the default calibrated on the real model (Task 14).
    return Settings(_env_file=None, retry_wait_seconds=0, evidence_min_score=0.30)


@pytest.fixture
def client(settings, services):
    """The app with fakes injected. Lifespan events don't run unless used as a context manager."""
    return TestClient(create_app(settings, services))


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
def deps(session_factory, store, settings, index):
    return IngestionDeps(
        session_factory=session_factory,
        file_store=store,
        embedder=FakeEmbedder(),
        index=index,
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


@pytest.fixture
def services(deps, retriever, fake_llm):
    """The same collaborators as deps, plus the retriever and the fake LLM."""
    return Services(
        **{field.name: getattr(deps, field.name) for field in fields(deps)},
        retriever=retriever,
        llm=fake_llm,
    )


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
def client_with_broken_qdrant(settings, services):
    """The app with a VectorIndex on a port nothing listens on, so every search fails.

    127.0.0.1 rather than localhost, because localhost stalls on this machine.
    """
    broken = VectorIndex(
        QdrantClient(url="http://127.0.0.1:1", check_compatibility=False, timeout=5),
        "unreachable",
        settings.embedding_dimension,
    )
    broken_services = replace(
        services, index=broken, retriever=DenseRetriever(services.embedder, broken)
    )
    yield TestClient(create_app(settings, broken_services))
    broken.client.close()


@pytest.fixture
def other_tenant(session):
    """A second tenant with its own upload source."""
    tenant = Tenant(name="Other")
    session.add(tenant)
    session.flush()
    session.add(Source(tenant_id=tenant.id, type="upload", name="Uploads"))
    session.commit()
    return tenant


@pytest.fixture(scope="session")
def test_collection():
    """One Qdrant collection for the whole run, deleted at the end."""
    settings = Settings(_env_file=None)
    client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
    vector_index = VectorIndex(client, f"test_{uuid4().hex}", settings.embedding_dimension)
    vector_index.ensure_collection()
    yield vector_index
    client.delete_collection(vector_index.collection)
    client.close()


@pytest.fixture
def index(test_collection):
    """The real Qdrant test collection, emptied before each test."""
    test_collection.client.delete(
        test_collection.collection,
        points_selector=models.FilterSelector(filter=models.Filter()),
        wait=True,
    )
    return test_collection


@pytest.fixture
def point():
    def make(tenant, principals):
        return IndexedPoint(
            chunk_id=uuid4(),
            vector=[1.0] + [0.0] * 1023,
            tenant_id=tenant,
            document_id=uuid4(),
            document_version_id=uuid4(),
            allowed_principals=list(principals),
        )

    return make


@pytest.fixture
def published_job(ingest):
    return ingest({"guide.md": b"# A\nhello\n"})


@pytest.fixture
def fail_upserts(index, monkeypatch):
    """Make the next `times` upserts raise a connection error, which counts as transient."""

    @contextmanager
    def failing(times):
        real_upsert = index.upsert
        remaining = [times]

        def upsert(points):
            if remaining[0] > 0:
                remaining[0] -= 1
                raise ConnectionError("Qdrant is unavailable (test)")
            return real_upsert(points)

        monkeypatch.setattr(index, "upsert", upsert)
        try:
            yield
        finally:
            monkeypatch.setattr(index, "upsert", real_upsert)

    return failing


@pytest.fixture
def retry(session, deps):
    """Reset a job to pending as the retry route does, run it, and return it refreshed."""

    def run(job):
        retry_job(session, job)
        run_ingestion(job.id, deps)
        session.refresh(job)
        return job

    return run


@pytest.fixture
def two_tenants(session):
    """Tenants A and B, each with an upload source."""
    for tenant_id, name in ((TENANT_A, "Tenant A"), (TENANT_B, "Tenant B")):
        session.add(Tenant(id=tenant_id, name=name))
        session.flush()
        session.add(Source(tenant_id=tenant_id, type="upload", name="Uploads"))
    session.commit()


@pytest.fixture
def retriever(deps):
    return DenseRetriever(deps.embedder, deps.index)


@pytest.fixture
def seed_chunk(session, index, two_tenants):
    """Publish one chunk to Postgres and Qdrant, in the current version of the path's document."""
    embedder = FakeEmbedder()

    def seed(text, tenant=DEFAULT_TENANT_ID, principals=("tenant",), path="a.md"):
        source = session.scalars(select(Source).filter_by(tenant_id=tenant, type="upload")).first()
        document = session.scalars(
            select(Document).filter_by(tenant_id=tenant, source_id=source.id, path=path)
        ).one_or_none()
        if document is None:
            document = Document(
                id=uuid4(),
                tenant_id=tenant,
                source_id=source.id,
                path=path,
                file_type="md",
                allowed_principals=list(principals),
            )
            session.add(document)
            session.flush()
            version = DocumentVersion(
                id=uuid4(),
                tenant_id=tenant,
                document_id=document.id,
                content_hash=uuid4().hex,
                storage_key=f"{tenant}/{'0' * 64}",
            )
            session.add(version)
            session.flush()
            document.current_version_id = version.id
        else:
            version = session.get(DocumentVersion, document.current_version_id)
        position = session.scalar(
            select(func.count()).select_from(Chunk).filter_by(document_version_id=version.id)
        )
        chunk = Chunk(
            id=uuid4(),
            tenant_id=tenant,
            document_version_id=version.id,
            position=position,
            content=text,
            token_count=len(text.split()),
            embedding_model=embedder.model_id,
            embedded_at=func.now(),
        )
        session.add(chunk)
        session.commit()
        index.upsert(
            [
                IndexedPoint(
                    chunk_id=chunk.id,
                    vector=embedder.embed_passages([text], 1)[0],
                    tenant_id=tenant,
                    document_id=document.id,
                    document_version_id=version.id,
                    allowed_principals=list(document.allowed_principals),
                )
            ]
        )
        return chunk

    return seed


@pytest.fixture
def supersede(session):
    """Make a new, empty version of the chunk's document current, so the chunk is stale."""

    def run(chunk):
        old = session.get(DocumentVersion, chunk.document_version_id)
        new = DocumentVersion(
            id=uuid4(),
            tenant_id=old.tenant_id,
            document_id=old.document_id,
            content_hash=uuid4().hex,
            storage_key=old.storage_key,
        )
        session.add(new)
        session.flush()
        session.get(Document, old.document_id).current_version_id = new.id
        session.commit()

    return run
