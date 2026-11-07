from uuid import UUID

from app.types import AccessScope

A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
VECTOR = [1.0] + [0.0] * 1023


def test_ensure_collection_is_idempotent(index):
    index.ensure_collection()
    index.ensure_collection()


def test_search_filters_by_tenant_and_principal(index, point):
    index.upsert([point(tenant=A, principals=["tenant"]), point(tenant=B, principals=["tenant"])])
    assert len(index.search(VECTOR, AccessScope(A, ("tenant",)), 10)) == 1
    assert index.search(VECTOR, AccessScope(A, ("team:x",)), 10) == []


def test_delete_version_removes_only_that_versions_points(index, point):
    keep, drop = point(tenant=A, principals=["tenant"]), point(tenant=A, principals=["tenant"])
    index.upsert([keep, drop])
    index.delete_version(drop.document_version_id)
    assert [chunk_id for chunk_id, _ in index.search(VECTOR, AccessScope(A, ("tenant",)), 10)] == [
        keep.chunk_id
    ]


def test_points_carry_no_chunk_text(index, published_job):
    payload = index.client.scroll(index.collection, with_payload=True)[0][0].payload
    assert set(payload) == {"tenant_id", "document_id", "document_version_id", "allowed_principals"}
