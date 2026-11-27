from uuid import uuid4

import pytest
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError
from opensearchpy.exceptions import ConnectionTimeout, RequestError, TransportError

from app.db.keyword_index import IndexedText, KeywordIndex, is_transient_opensearch_error
from app.types import AccessScope
from tests.tenants import TENANT_A, TENANT_B

SCOPE_A = AccessScope(TENANT_A, ("tenant",))


def _text(content, headings="", tenant=TENANT_A, principals=("tenant",), version=None):
    return IndexedText(
        chunk_id=uuid4(),
        content=content,
        headings=headings,
        tenant_id=tenant,
        document_id=uuid4(),
        document_version_id=version or uuid4(),
        allowed_principals=list(principals),
    )


def _ids(hits):
    return [chunk_id for chunk_id, _ in hits]


def test_a_word_in_the_content_finds_the_chunk(keyword_index):
    pods = _text("A Pod is the smallest deployable unit of computing")
    keyword_index.upsert([pods, _text("Services expose an application on the network")])
    hits = keyword_index.search("deployable", SCOPE_A, 10)
    assert _ids(hits) == [pods.chunk_id]
    assert hits[0][1] > 0


def test_a_heading_match_outranks_a_body_match(keyword_index):
    in_heading = _text("Pods move through phases until they stop.", headings="Pod lifecycle")
    in_body = _text("Pods move through a lifecycle until they stop.", headings="Overview")
    keyword_index.upsert([in_body, in_heading])
    assert _ids(keyword_index.search("lifecycle", SCOPE_A, 10))[0] == in_heading.chunk_id


@pytest.mark.parametrize(
    ("term", "exact", "near"),
    [
        # The near chunk is shorter and has the same two words side by side, so it matches
        # the split parts as well as the exact one does. Only the whole identifier, which the
        # ident field keeps from inside backticks or before a full stop, puts the exact one first.
        (
            "kube-scheduler",
            "Pods are placed onto nodes by the `kube-scheduler` component.",
            "The kube scheduler.",
        ),
        (
            "kube-scheduler",
            "Pods are placed onto nodes by the kube-scheduler.",
            "The kube scheduler.",
        ),
        (
            "spec.nodeName",
            "Setting `spec.nodeName` binds a Pod to one node directly",
            "The node name and the Pod spec are both shown here",
        ),
    ],
    ids=["hyphenated-in-backticks", "hyphenated-at-sentence-end", "dotted"],
)
def test_an_identifier_finds_its_chunk_first(keyword_index, term, exact, near):
    wanted = _text(exact)
    keyword_index.upsert([_text(near), wanted])
    assert _ids(keyword_index.search(term, SCOPE_A, 10))[0] == wanted.chunk_id


def test_another_tenants_chunk_never_comes_back(keyword_index):
    own = _text("tenant secret plans")
    keyword_index.upsert([_text("tenant secret plans", tenant=TENANT_B), own])
    assert _ids(keyword_index.search("secret plans", SCOPE_A, 10)) == [own.chunk_id]


def test_a_chunk_without_a_shared_principal_never_comes_back(keyword_index):
    keyword_index.upsert([_text("restricted runbook", principals=("group:sre",))])
    assert keyword_index.search("restricted runbook", SCOPE_A, 10) == []
    sre = AccessScope(TENANT_A, ("tenant", "group:sre"))
    assert len(keyword_index.search("restricted runbook", sre, 10)) == 1


def test_delete_version_removes_only_that_version(keyword_index):
    old, new = uuid4(), uuid4()
    keyword_index.upsert([_text("rollout notes", version=old), _text("rollout notes", version=new)])
    keyword_index.delete_version(old)
    assert keyword_index.count() == 1
    assert len(keyword_index.search("rollout", SCOPE_A, 10)) == 1


def test_upserting_a_chunk_twice_keeps_one_copy(keyword_index):
    chunk = _text("idempotent ingestion")
    keyword_index.upsert([chunk])
    keyword_index.upsert([chunk])
    assert keyword_index.count() == 1


@pytest.mark.parametrize("query", ["AND OR (", "foo:bar", "*", "   "])
def test_query_syntax_never_raises(keyword_index, query):
    keyword_index.upsert([_text("foo bar baz"), _text("something else entirely")])
    assert isinstance(keyword_index.search(query, SCOPE_A, 10), list)


def test_a_wildcard_is_not_a_match_everything_query(keyword_index):
    keyword_index.upsert([_text("* first item\n* second item"), _text("something else")])
    assert len(keyword_index.search("*", SCOPE_A, 10)) < keyword_index.count()


def test_a_blank_query_returns_nothing_without_calling_opensearch(keyword_index, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("OpenSearch was called")

    monkeypatch.setattr(keyword_index.client, "search", refuse)
    assert keyword_index.search("  \n ", SCOPE_A, 10) == []


def test_ping_reports_a_live_server(keyword_index):
    assert keyword_index.ping() is True


@pytest.mark.parametrize(
    ("error", "transient"),
    [
        (OpenSearchConnectionError("N/A", "refused", None), True),
        (ConnectionTimeout("TIMEOUT", "timed out", None), True),
        (TransportError(429, "too_many_requests", {}), True),
        (TransportError(503, "unavailable", {}), True),
        (RequestError(400, "parsing_exception", {}), False),
        (ValueError("bad input"), False),
    ],
    ids=["connection", "timeout", "429", "503", "400", "other"],
)
def test_transient_errors_are_connection_failures_429_and_5xx(error, transient):
    assert is_transient_opensearch_error(error) is transient


def test_an_upsert_into_a_missing_index_creates_it_with_the_real_mapping(opensearch_client):
    # If OpenSearch was down when the API started, the first publish meets no index. Left to
    # OpenSearch's auto-create, the index would get a dynamic mapping: principals analysed as
    # text and no identifier analyzer, which ensure_index would then never repair.
    index = KeywordIndex(opensearch_client, f"chunks_test_{uuid4().hex}")
    try:
        sre = _text("kube-scheduler picks a node", principals=("group:sre",))
        index.upsert([sre])
        mapping = opensearch_client.indices.get_mapping(index=index.index)[index.index]
        fields = mapping["mappings"]["properties"]
        assert fields["allowed_principals"]["type"] == "keyword"
        assert fields["tenant_id"]["type"] == "keyword"
        assert _ids(index.search("kube-scheduler", AccessScope(TENANT_A, ("group:sre",)), 10)) == [
            sre.chunk_id
        ]
        assert index.search("kube-scheduler", AccessScope(TENANT_A, ("group",)), 10) == []
    finally:
        opensearch_client.indices.delete(index=index.index, ignore_unavailable=True)
