from uuid import uuid4

from sqlalchemy import select

from app.db.constants import DEFAULT_UPLOAD_SOURCE_ID
from app.db.models import Document


def source_body(**fields):
    body = {
        "name": "k8s",
        "repository": "https://github.com/kubernetes/website.git",
        "branch": "main",
        "include_paths": ["content/en/docs/concepts/**"],
    }
    return {**body, **fields}


def test_create_source_accepts_a_pasted_url(client):
    response = client.post("/api/sources", json=source_body())
    assert response.status_code == 201
    assert response.json()["config"] == {
        "repository": "kubernetes/website",
        "branch": "main",
        "include_paths": ["content/en/docs/concepts/**"],
    }


def test_created_source_is_listed(client):
    created = client.post("/api/sources", json=source_body()).json()
    assert created["id"] in [source["id"] for source in client.get("/api/sources").json()]


def test_blank_include_paths_mean_the_whole_repository(client):
    body = source_body(include_paths=["  ", ""])
    assert client.post("/api/sources", json=body).json()["config"]["include_paths"] == ["**"]


def test_include_paths_are_trimmed(client):
    body = source_body(include_paths=[" /docs/** ", "src/"])
    assert client.post("/api/sources", json=body).json()["config"]["include_paths"] == [
        "docs/**",
        "src/",
    ]


def test_blank_name_defaults_to_the_repository(client):
    assert client.post("/api/sources", json=source_body(name=" ")).json()["name"] == (
        "kubernetes/website"
    )


def test_invalid_repository_is_422(client):
    body = {"name": "x", "repository": "nope", "branch": "main", "include_paths": ["**"]}
    assert client.post("/api/sources", json=body).status_code == 422


def test_invalid_repository_message_says_what_to_enter(client):
    body = source_body(repository="nope")
    assert "owner/name" in client.post("/api/sources", json=body).json()["detail"]


def test_blank_branch_is_422(client):
    assert client.post("/api/sources", json=source_body(branch=" ")).status_code == 422


def test_sync_while_a_job_is_open_is_409(client, github_source, make_job):
    make_job("running", source=github_source)
    assert client.post(f"/api/sources/{github_source.id}/sync").status_code == 409


def test_sync_on_an_upload_source_is_409(client):
    assert client.post(f"/api/sources/{DEFAULT_UPLOAD_SOURCE_ID}/sync").status_code == 409


def test_sync_on_an_unknown_source_is_404(client):
    assert client.post(f"/api/sources/{uuid4()}/sync").status_code == 404


def test_sync_ingests_the_included_files(client, github_source, fake_repo, session):
    response = client.post(f"/api/sources/{github_source.id}/sync")
    assert response.status_code == 202
    job = client.get(f"/api/jobs/{response.json()['job_id']}").json()
    assert (job["status"], job["file_counts"]["processed"]) == ("succeeded", 1)
    paths = session.scalars(select(Document.path).filter_by(source_id=github_source.id)).all()
    assert paths == ["docs/a.md"]


def test_github_answer_links_to_the_commit(client, github_source, fake_llm, fake_repo):
    client.post(f"/api/sources/{github_source.id}/sync")
    fake_llm.returns("answered", "Yes [1].")
    citation = client.post("/api/questions", json={"question": fake_repo.question}).json()[
        "citations"
    ][0]
    assert citation["url"].startswith("https://github.com/o/r/blob/abc/docs/a.md#L")
