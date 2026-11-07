import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.base import Base
from app.db.constants import DEFAULT_TENANT_ID, DEFAULT_UPLOAD_SOURCE_ID
from app.db.models import DocumentVersion, Source, Tenant


def test_migration_seeds_default_tenant_and_upload_source(session):
    assert session.get(Tenant, DEFAULT_TENANT_ID) is not None
    assert session.get(Source, DEFAULT_UPLOAD_SOURCE_ID).type == "upload"


def test_allowed_principals_defaults_to_tenant(session, make_document):
    assert make_document().allowed_principals == ["tenant"]


def test_document_path_is_unique_per_source(session, make_document):
    make_document(path="a.md")
    with pytest.raises(IntegrityError):
        make_document(path="a.md")


def test_version_hash_is_unique_per_document(session, make_document, make_version):
    doc = make_document()
    make_version(doc, content_hash="h")
    with pytest.raises(IntegrityError):
        make_version(doc, content_hash="h")


def test_chunk_position_is_unique_per_version(session, make_version, make_chunk):
    version = make_version()
    make_chunk(version, position=0)
    with pytest.raises(IntegrityError):
        make_chunk(version, position=0)


@pytest.mark.parametrize("status", ["pending", "running", "awaiting_embedding"])
def test_only_one_open_job_per_source(session, make_job, status):
    make_job(status=status)
    with pytest.raises(IntegrityError):
        make_job(status="pending")


def test_finished_job_allows_a_new_job(session, make_job):
    make_job(status="succeeded")
    make_job(status="pending")


def test_models_match_the_migrations(migrated_session_factory):
    engine = migrated_session_factory.kw["bind"]
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_deferred_version_records_the_job_waiting_for_it(session, deferred_job):
    version = session.scalars(select(DocumentVersion)).one()
    assert version.awaiting_job_id == deferred_job.id
