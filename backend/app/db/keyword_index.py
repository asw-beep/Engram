"""The OpenSearch projection: one document per chunk, with its text, headings and permissions.

Unlike Qdrant it stores chunk text, but it is still a projection: PostgreSQL is canonical,
and the whole index can be rebuilt from it.
"""

from dataclasses import dataclass
from uuid import UUID

from opensearchpy import OpenSearch, helpers
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError
from opensearchpy.exceptions import RequestError, TransportError

from app.types import AccessScope

# Field boosts for the BM25 query: a heading match counts twice a body match.
SEARCH_FIELDS = ["content", "content.ident", "headings^2", "headings.ident^2"]

# Text is indexed twice. The standard analyzer splits words for ordinary prose. The ident
# analyzer keeps identifiers such as kube-scheduler and spec.nodeName whole as well as split,
# so an exact term scores above text that only shares its parts. Its character filter turns
# Markdown punctuation (backticks, quotes, brackets, bullets) and any ".", "-" or "/" not
# inside a word into spaces, so `spec.nodeName` and "kube-scheduler." index as the bare
# identifier and a lone "*" is never a token.
_SETTINGS = {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "analysis": {
        "char_filter": {
            "ident_punctuation": {
                "type": "pattern_replace",
                "pattern": r"[^\w./-]|(?<!\w)[./-]|[./-](?!\w)",
                "replacement": " ",
            }
        },
        "filter": {"ident_parts": {"type": "word_delimiter_graph", "preserve_original": True}},
        "analyzer": {
            "ident": {
                "type": "custom",
                "char_filter": ["ident_punctuation"],
                "tokenizer": "whitespace",
                "filter": ["ident_parts", "lowercase", "flatten_graph"],
            }
        },
    },
}


def _text_field() -> dict:
    return {
        "type": "text",
        "analyzer": "standard",
        "fields": {"ident": {"type": "text", "analyzer": "ident"}},
    }


_MAPPINGS = {
    "dynamic": "strict",
    "properties": {
        "content": _text_field(),
        "headings": _text_field(),
        "tenant_id": {"type": "keyword"},
        "document_id": {"type": "keyword"},
        "document_version_id": {"type": "keyword"},
        "allowed_principals": {"type": "keyword"},
    },
}


@dataclass(frozen=True)
class IndexedText:
    chunk_id: UUID
    content: str
    headings: str
    tenant_id: UUID
    document_id: UUID
    document_version_id: UUID
    allowed_principals: list[str]


def is_transient_opensearch_error(error: Exception) -> bool:
    """Connection failures, timeouts, 429 and 5xx; worth retrying."""
    if isinstance(error, OpenSearchConnectionError | ConnectionError | TimeoutError):
        return True
    if isinstance(error, TransportError) and isinstance(error.status_code, int):
        return error.status_code == 429 or error.status_code >= 500
    return False


class KeywordIndex:
    def __init__(self, client: OpenSearch, index: str):
        self.client = client
        self.index = index

    def ensure_index(self) -> None:
        if self.client.indices.exists(index=self.index):
            return
        try:
            self.client.indices.create(
                index=self.index, body={"settings": _SETTINGS, "mappings": _MAPPINGS}
            )
        except RequestError as error:
            # Another process created it between the check and the create.
            if error.error != "resource_already_exists_exception":
                raise

    def upsert(self, items: list[IndexedText]) -> None:
        """Index each chunk under its ID, so a repeat overwrites rather than duplicates."""
        if not items:
            return
        actions = [
            {
                "_op_type": "index",
                "_index": self.index,
                "_id": str(item.chunk_id),
                "_source": {
                    "content": item.content,
                    "headings": item.headings,
                    "tenant_id": str(item.tenant_id),
                    "document_id": str(item.document_id),
                    "document_version_id": str(item.document_version_id),
                    "allowed_principals": list(item.allowed_principals),
                },
            }
            for item in items
        ]
        helpers.bulk(self.client, actions, refresh="wait_for")

    def delete_version(self, version_id: UUID) -> None:
        self.client.delete_by_query(
            index=self.index,
            body={"query": {"term": {"document_version_id": str(version_id)}}},
            refresh=True,
            conflicts="proceed",
        )

    def search(self, query: str, scope: AccessScope, limit: int) -> list[tuple[UUID, float]]:
        """BM25 matches the scope may see: its tenant, and at least one shared principal.

        The query is matched as plain text, never parsed as query syntax.
        """
        if not query.strip():
            return []
        body = {
            "size": limit,
            "_source": False,
            "query": {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": query,
                            "fields": SEARCH_FIELDS,
                            "type": "most_fields",
                        }
                    },
                    "filter": [
                        {"term": {"tenant_id": str(scope.tenant_id)}},
                        {"terms": {"allowed_principals": list(scope.principals)}},
                    ],
                }
            },
        }
        response = self.client.search(index=self.index, body=body)
        return [(UUID(hit["_id"]), hit["_score"]) for hit in response["hits"]["hits"]]

    def count(self) -> int:
        return self.client.count(index=self.index)["count"]

    def ping(self) -> bool:
        return bool(self.client.ping())
