from uuid import uuid4

from sqlalchemy import select

from app.db.constants import DEFAULT_UPLOAD_SOURCE_ID
from app.db.models import Document, IngestionJob, Source


def upload(client, name="guide.md", body=b"# A\nx\n", source=DEFAULT_UPLOAD_SOURCE_ID):
    return client.post(f"/api/sources/{source}/documents", files={"files": (name, body)})


def test_upload_starts_a_job(client):
    response = upload(client)
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert job["file_counts"]["processed"] == 1


def test_defer_embedding_is_saved_on_the_job(client, session):
    response = client.post(
        f"/api/sources/{DEFAULT_UPLOAD_SOURCE_ID}/documents",
        files={"files": ("guide.md", b"# A\nx\n")},
        data={"defer_embedding": "true"},
    )
    assert response.status_code == 202
    assert session.scalars(select(IngestionJob.input)).one()["defer_embedding"] is True


def test_unsupported_type_is_rejected_without_a_job(client):
    assert upload(client, name="a.txt").status_code == 415
    assert client.get("/api/jobs").json() == []


def test_oversized_file_is_rejected(client):
    body = b"x" * (25 * 1024 * 1024 + 1)
    assert upload(client, body=body).status_code == 413


def test_duplicate_names_in_one_upload_are_rejected_without_a_job(client):
    files = [("files", ("a/guide.md", b"# A\nx\n")), ("files", ("b/guide.md", b"# B\ny\n"))]
    response = client.post(f"/api/sources/{DEFAULT_UPLOAD_SOURCE_ID}/documents", files=files)
    assert response.status_code == 400
    assert client.get("/api/jobs").json() == []


def test_filename_is_reduced_to_its_base_name(client, session):
    upload(client, name="../../evil.md")
    assert session.scalars(select(Document.path)).one() == "evil.md"


def test_unknown_source_is_404(client):
    assert upload(client, source=uuid4()).status_code == 404


def test_other_tenants_source_is_404(client, other_tenant, session):
    other_source = session.scalars(select(Source).filter_by(tenant_id=other_tenant.id)).one()
    assert upload(client, source=other_source.id).status_code == 404


def test_second_open_job_is_a_conflict(client, make_job):
    make_job(status="running")
    response = upload(client)
    assert response.status_code == 409
    assert "job_id" in response.json()["detail"]
