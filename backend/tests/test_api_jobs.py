from fastapi.testclient import TestClient

from app.main import create_app


def test_retry_reruns_a_failed_job(client, make_job):
    job = make_job(status="failed")
    assert client.post(f"/api/jobs/{job.id}/retry").status_code == 202


def test_retry_rejects_a_succeeded_job(client, make_job):
    job = make_job(status="succeeded")
    assert client.post(f"/api/jobs/{job.id}/retry").status_code == 409


def test_startup_marks_unfinished_jobs_interrupted(settings, services, make_job):
    job = make_job(status="running")
    with TestClient(create_app(settings, services)) as fresh:
        assert fresh.get(f"/api/jobs/{job.id}").json()["status"] == "interrupted"


def test_other_tenants_job_is_404(client, make_job, other_tenant):
    job = make_job(tenant=other_tenant)
    assert client.get(f"/api/jobs/{job.id}").status_code == 404


def test_job_list_shows_only_this_tenants_jobs(client, make_job, other_tenant):
    mine = make_job(status="succeeded")
    make_job(status="succeeded", tenant=other_tenant)
    assert [job["id"] for job in client.get("/api/jobs").json()] == [str(mine.id)]


def test_retry_while_another_job_is_open_is_a_conflict(client, make_job):
    failed = make_job(status="failed")
    running = make_job(status="running")
    response = client.post(f"/api/jobs/{failed.id}/retry")
    assert response.status_code == 409
    assert response.json()["detail"]["job_id"] == str(running.id)
