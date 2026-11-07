"""The Qdrant projection: one point per chunk, holding IDs and permissions but no text."""

from dataclasses import dataclass
from uuid import UUID

import httpx
from qdrant_client import QdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.types import AccessScope


@dataclass(frozen=True)
class IndexedPoint:
    chunk_id: UUID
    vector: list[float]
    tenant_id: UUID
    document_id: UUID
    document_version_id: UUID
    allowed_principals: list[str]


def is_transient_qdrant_error(error: Exception) -> bool:
    if isinstance(error, UnexpectedResponse):
        return error.status_code == 429 or error.status_code >= 500
    return isinstance(
        error, ResponseHandlingException | httpx.TransportError | ConnectionError | TimeoutError
    )


class VectorIndex:
    def __init__(self, client: QdrantClient, collection: str, dimension: int):
        self.client = client
        self.collection = collection
        self.dimension = dimension

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(
                    size=self.dimension, distance=models.Distance.COSINE
                ),
            )
        self.client.create_payload_index(
            self.collection,
            "tenant_id",
            models.KeywordIndexParams(type=models.KeywordIndexType.KEYWORD, is_tenant=True),
        )
        self.client.create_payload_index(
            self.collection, "allowed_principals", models.PayloadSchemaType.KEYWORD
        )

    def upsert(self, points: list[IndexedPoint]) -> None:
        if not points:
            return
        self.client.upsert(
            self.collection,
            points=[
                models.PointStruct(
                    id=str(point.chunk_id),
                    vector=point.vector,
                    payload={
                        "tenant_id": str(point.tenant_id),
                        "document_id": str(point.document_id),
                        "document_version_id": str(point.document_version_id),
                        "allowed_principals": list(point.allowed_principals),
                    },
                )
                for point in points
            ],
            wait=True,
        )

    def delete_version(self, version_id: UUID) -> None:
        self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_version_id",
                            match=models.MatchValue(value=str(version_id)),
                        )
                    ]
                )
            ),
            wait=True,
        )

    def search(
        self, vector: list[float], scope: AccessScope, limit: int
    ) -> list[tuple[UUID, float]]:
        """Nearest chunks the scope may see: its tenant, and at least one shared principal."""
        response = self.client.query_points(
            collection_name=self.collection,
            query=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id", match=models.MatchValue(value=str(scope.tenant_id))
                    ),
                    models.FieldCondition(
                        key="allowed_principals", match=models.MatchAny(any=list(scope.principals))
                    ),
                ]
            ),
            limit=limit,
            with_payload=False,
        )
        return [(UUID(str(point.id)), point.score) for point in response.points]

    def count(self) -> int:
        return self.client.count(self.collection, exact=True).count
