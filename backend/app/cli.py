"""Commands for the Kaggle route (spec section 5), run from backend/:

uv run python -m app.cli export-chunks --job <id> --out <file>
uv run python -m app.cli import-vectors --job <id> --in <dir>
"""

import argparse
import sys
from pathlib import Path
from uuid import UUID

from qdrant_client import QdrantClient
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.db.base import build_session_factory
from app.db.models import IngestionJob
from app.db.vector_index import VectorIndex
from app.ingestion.transfer import TransferError, export_chunks, import_vectors


def run_cli(
    argv: list[str],
    settings: Settings,
    session_factory: sessionmaker[Session],
    index: VectorIndex,
) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="Embed a waiting job's chunks on Kaggle."
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
    args = parser.parse_args(argv)

    try:
        with session_factory() as session:
            if args.command == "export-chunks":
                count = export_chunks(session, args.job, args.out, settings)
                print(f"Wrote {count} chunk{'' if count == 1 else 's'} to {args.out}")
            else:
                import_vectors(session, args.job, args.in_dir, index, settings)
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
    try:
        return run_cli(sys.argv[1:], settings, build_session_factory(settings.database_url), index)
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
