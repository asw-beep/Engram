from uuid import UUID

from sqlalchemy import select

from app.cli import run_cli
from app.db.models import Chunk, Document
from app.ingestion.reindex import reindex_keyword


def _current_chunks(session):
    return {
        chunk.id: (chunk, document)
        for chunk, document in session.execute(
            select(Chunk, Document).join(
                Document, Document.current_version_id == Chunk.document_version_id
            )
        )
    }


def _entries(keyword_index):
    response = keyword_index.client.search(
        index=keyword_index.index, body={"query": {"match_all": {}}, "size": 100}
    )
    return {UUID(hit["_id"]): hit["_source"] for hit in response["hits"]["hits"]}


def _empty(keyword_index):
    keyword_index.client.delete_by_query(
        index=keyword_index.index, body={"query": {"match_all": {}}}, refresh=True
    )
    assert keyword_index.count() == 0


def test_reindex_restores_exactly_the_current_versions_chunks(session, ingest, keyword_index):
    ingest({"a.md": b"# A\nalpha\n", "b.md": b"# B\n## Two\nbeta\n"})
    ingest({"a.md": b"# A\nalpha again\n"})
    ingest({"c.md": b"# C\nwaiting\n"}, defer_embedding=True)
    current = _current_chunks(session)
    # Four chunks in all: a.md's old version and c.md, which isn't published, stay out.
    assert len(current) == 2 and len(session.scalars(select(Chunk.id)).all()) == 4
    _empty(keyword_index)

    assert reindex_keyword(session, keyword_index, batch_size=1) == 2

    entries = _entries(keyword_index)
    assert entries.keys() == current.keys()
    for chunk_id, (chunk, document) in current.items():
        assert entries[chunk_id] == {
            "content": chunk.content,
            "headings": " > ".join(chunk.heading_path),
            "tenant_id": str(document.tenant_id),
            "document_id": str(document.id),
            "document_version_id": str(document.current_version_id),
            "allowed_principals": list(document.allowed_principals),
        }


def test_reindex_keeps_each_tenants_chunks_under_that_tenant(
    session, ingest, keyword_index, other_tenant, make_document, make_version, make_chunk
):
    ingest({"a.md": b"# A\nalpha\n"})
    own = session.scalars(select(Chunk)).one()
    document = make_document(tenant=other_tenant)
    version = make_version(document)
    other = make_chunk(version, content="other tenant text")
    document.current_version_id = version.id
    session.commit()
    _empty(keyword_index)

    assert reindex_keyword(session, keyword_index) == 2
    tenants = {chunk_id: entry["tenant_id"] for chunk_id, entry in _entries(keyword_index).items()}
    assert tenants == {own.id: str(own.tenant_id), other.id: str(other_tenant.id)}


def test_reindex_creates_a_missing_index(session, ingest, keyword_index):
    ingest({"a.md": b"# A\nalpha\n"})
    keyword_index.client.indices.delete(index=keyword_index.index)
    assert reindex_keyword(session, keyword_index) == 1
    assert keyword_index.count() == 1


def test_cli_reindex_keyword_prints_the_count(
    session, ingest, settings, session_factory, index, keyword_index, capsys
):
    ingest({"a.md": b"# A\nalpha\n", "b.md": b"# B\nbeta\n"})
    _empty(keyword_index)
    assert run_cli(["reindex-keyword"], settings, session_factory, index, keyword_index) == 0
    assert capsys.readouterr().out.strip() == "Indexed 2 chunks."
    assert keyword_index.count() == 2
