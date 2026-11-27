"""Commands run from backend/: the Kaggle route (spec section 5) and the keyword rebuild.

uv run python -m app.cli export-chunks --job <id> --out <file>
uv run python -m app.cli import-vectors --job <id> --in <dir>
uv run python -m app.cli reindex-keyword
"""

import argparse
import sys
from pathlib import Path
from uuid import UUID

from opensearchpy import OpenSearch
from qdrant_client import QdrantClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.base import build_session_factory
from app.db.keyword_index import KeywordIndex
from app.db.models import IngestionJob
from app.db.vector_index import VectorIndex
from app.ingestion.reindex import reindex_keyword
from app.ingestion.transfer import TransferError, export_chunks, import_vectors


def run_cli(
    argv: list[str],
    settings: Settings,
    session_factory: sessionmaker[Session],
    index: VectorIndex,
    keyword_index: KeywordIndex,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Embed a waiting job's chunks on Kaggle, or rebuild the keyword index.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser(
        "export-chunks", help="write a waiting job's chunks for the Kaggle notebook"
    )
    export.add_argument("--job", type=UUID, required=True)
    export.add_argument("--out", type=Path, required=True)
    imports = commands.add_parser(
        "import-vectors", help="publish the notebook's vectors and finish the job"
    )
    imports.add_argument("--job", type=UUID, required=True)
    imports.add_argument("--in", dest="in_dir", type=Path, required=True)
    commands.add_parser(
        "reindex-keyword",
        help="rebuild the keyword index from every current version in PostgreSQL",
    )
    args = parser.parse_args(argv)

    try:
        with session_factory() as session:
            if args.command == "export-chunks":
                count = export_chunks(session, args.job, args.out, settings)
                print(f"Wrote {count} chunk{'' if count == 1 else 's'} to {args.out}")
            elif args.command == "reindex-keyword":
                count = reindex_keyword(
                    session, keyword_index, retry_wait=settings.retry_wait_seconds
                )
                print(f"Indexed {count} chunk{'' if count == 1 else 's'}.")
            else:
                import_vectors(session, args.job, args.in_dir, index, keyword_index, settings)
                status = session.get(IngestionJob, args.job).status
                print(f"Imported vectors. Job {args.job} is {status}.")
    except TransferError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    settings = get_settings()
    client = QdrantClient(url=settings.qdrant_url, check_compatibility=False)
    index = VectorIndex(client, settings.qdrant_collection, settings.embedding_dimension)
    search = OpenSearch(hosts=[settings.opensearch_url], timeout=30)
    keyword_index = KeywordIndex(search, settings.opensearch_index)
    try:
        return run_cli(
            sys.argv[1:],
            settings,
            build_session_factory(settings.database_url),
            index,
            keyword_index,
        )
    finally:
        client.close()
        search.close()


if __name__ == "__main__":
    sys.exit(main())
