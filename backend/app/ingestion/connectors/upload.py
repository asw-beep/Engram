from app.ingestion.types import FetchedFile, SourceItem
from app.storage.files import FileStore


class UploadConnector:
    """Reads files that the upload route already saved, as listed in the job input."""

    def __init__(self, file_store: FileStore, uploads: list[dict]):
        self._file_store = file_store
        self._uploads = uploads

    def list_items(self) -> list[SourceItem]:
        return [
            SourceItem(path=upload["path"], storage_key=upload["storage_key"])
            for upload in self._uploads
        ]

    def fetch(self, item: SourceItem) -> FetchedFile:
        return FetchedFile(item, self._file_store.get(item.storage_key))

    def close(self) -> None:
        pass
