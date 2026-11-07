from collections.abc import Iterable
from typing import Protocol

from app.ingestion.types import FetchedFile, SourceItem


class ConnectorError(Exception):
    """The source as a whole can't be read. The message is shown to the user."""


class Connector(Protocol):
    def list_items(self) -> Iterable[SourceItem]: ...

    def fetch(self, item: SourceItem) -> FetchedFile: ...

    def close(self) -> None: ...
