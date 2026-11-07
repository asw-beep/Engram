"""Public GitHub repositories, read from one tarball of the branch's newest commit.

The tarball is saved to a temporary file and its members are read in place, never extracted,
so names inside the archive can't write anywhere on disk.
"""

import os
import re
import tarfile
import tempfile
import zlib
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from urllib.parse import quote

import httpx

from app.ingestion.connectors.base import ConnectorError, FileTooLarge
from app.ingestion.connectors.globs import matches_include
from app.ingestion.parsers import SUPPORTED_EXTENSIONS
from app.ingestion.types import FetchedFile, SourceItem
from app.retrying import retry_transient

API = "https://api.github.com"
_OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*")
_NAME = re.compile(r"[A-Za-z0-9._-]+")
_URL_PREFIXES = ("https://github.com/", "http://github.com/", "github.com/", "git@github.com:")
# A subset of git's ref-name rules: enough to keep the name a single, plain URL path.
_BAD_BRANCH = re.compile(r"\.\.|[\s~^:?*\[\\]|^[/-]|/$|\.lock$|@\{|//")
_SHA = re.compile(r"[0-9a-fA-F]{1,64}")
_CHUNK = 1024 * 1024


def normalize_repository(value: str) -> str:
    """owner/name from owner/name, an https URL or an SSH remote."""
    text = value.strip()
    for prefix in _URL_PREFIXES:
        if text.lower().startswith(prefix):
            text = text[len(prefix) :]
            break
    text = text.rstrip("/").removesuffix(".git")
    parts = text.split("/")
    if (
        len(parts) != 2
        or not _OWNER.fullmatch(parts[0])
        or not _NAME.fullmatch(parts[1])
        or parts[1] in (".", "..")
    ):
        raise ValueError("Enter a GitHub repository as owner/name, or paste its URL")
    return f"{parts[0]}/{parts[1]}"


def normalize_branch(value: str) -> str:
    branch = value.strip()
    if not branch or _BAD_BRANCH.search(branch):
        raise ValueError("Enter a branch name, for example main")
    return branch


class _ServerError(Exception):
    """GitHub answered 5xx. Retried, then reported as unavailable."""

    def __init__(self, status: int):
        super().__init__(f"HTTP {status}")
        self.status = status


def _is_transient(error: Exception) -> bool:
    return isinstance(error, (_ServerError, httpx.TransportError))


class GitHubConnector:
    def __init__(
        self,
        repository: str,
        branch: str,
        include_paths: list[str],
        token: str | None,
        client: httpx.Client,
        max_file_bytes: int,
        *,
        temp_dir: Path,
        retry_wait: float = 1.0,
    ):
        self.repository = repository
        self.branch = branch
        self.include_paths = include_paths
        self.max_file_bytes = max_file_bytes
        self.archive_path: Path | None = None
        self._client = client
        self._token = token
        self._temp_dir = Path(temp_dir)
        self._retry_wait = retry_wait
        self._archive: tarfile.TarFile | None = None
        self._members: dict[str, tarfile.TarInfo] = {}

    def list_items(self) -> list[SourceItem]:
        sha = self._resolve_commit()
        self._download(sha)
        try:
            self._archive = tarfile.open(self.archive_path, "r:gz")
            items = []
            for member in self._archive:
                path = _repository_path(member)
                if path is None or PurePosixPath(path).suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue
                if matches_include(path, self.include_paths):
                    self._members[path] = member
                    items.append(SourceItem(path=path, revision=sha))
        except (tarfile.TarError, OSError, EOFError, zlib.error) as error:
            raise ConnectorError("could not read the repository archive from GitHub") from error
        return items

    def fetch(self, item: SourceItem) -> FetchedFile:
        member = self._members[item.path]
        if member.size > self.max_file_bytes:
            raise FileTooLarge(f"file is over {_size_text(self.max_file_bytes)}")
        try:
            reader = self._archive.extractfile(member)
            content = reader.read() if reader is not None else b""
        except (tarfile.TarError, OSError, EOFError, zlib.error) as error:
            raise ConnectorError("could not read the repository archive from GitHub") from error
        return FetchedFile(item, content)

    def close(self) -> None:
        if self._archive is not None:
            self._archive.close()
            self._archive = None
        if self.archive_path is not None:
            self.archive_path.unlink(missing_ok=True)

    def _resolve_commit(self) -> str:
        url = f"{API}/repos/{self.repository}/commits/{quote(self.branch, safe='/')}"
        response = self._call(
            lambda: self._checked(
                self._client.get(url, headers=self._headers("application/vnd.github.sha"))
            )
        )
        sha = response.text.strip()
        if not _SHA.fullmatch(sha):
            raise ConnectorError("GitHub returned an unexpected commit id")
        return sha

    def _download(self, sha: str) -> None:
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(prefix="github-", suffix=".tar.gz", dir=self._temp_dir)
        os.close(handle)
        self.archive_path = Path(name)
        url = f"{API}/repos/{self.repository}/tarball/{sha}"

        def download() -> None:
            headers = self._headers("application/vnd.github+json")
            with self._client.stream("GET", url, headers=headers, follow_redirects=True) as reply:
                self._checked(reply)
                with self.archive_path.open("wb") as file:
                    for chunk in reply.iter_bytes(_CHUNK):
                        file.write(chunk)

        self._call(download)

    def _call[T](self, fn: Callable[[], T]) -> T:
        try:
            return retry_transient(fn, _is_transient, wait_base=self._retry_wait)
        except _ServerError as error:
            raise ConnectorError(
                f"GitHub is unavailable (HTTP {error.status}). Try again later"
            ) from error
        except httpx.TransportError as error:
            raise ConnectorError(
                "GitHub is unavailable (no connection). Try again later"
            ) from error

    def _headers(self, accept: str) -> dict[str, str]:
        headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def _checked(self, response: httpx.Response) -> httpx.Response:
        status = response.status_code
        if status < 400:
            return response
        if status >= 500:
            raise _ServerError(status)
        if status == 404:
            raise ConnectorError(f"Repository not found or private: {self.repository}")
        if status == 422:
            raise ConnectorError(f"Branch {self.branch} not found in {self.repository}")
        if status == 401:
            raise ConnectorError("GitHub rejected the token (HTTP 401). Check GITHUB_TOKEN")
        limited = response.headers.get("x-ratelimit-remaining") == "0"
        if status == 429 or (status == 403 and (limited or "retry-after" in response.headers)):
            raise ConnectorError(
                "GitHub rate limit reached. Try again later, or set GITHUB_TOKEN for a higher limit"
            )
        raise ConnectorError(f"GitHub refused the request for {self.repository} (HTTP {status})")


def _repository_path(member: tarfile.TarInfo) -> str | None:
    """The path inside the repository, without GitHub's top folder. None for anything that
    isn't a regular file, or whose name would leave the repository."""
    if not member.isfile():
        return None
    parts = member.name.split("/")[1:]
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    return "/".join(parts)


def _size_text(limit: int) -> str:
    return f"{limit // 2**20} MB" if limit >= 2**20 else f"{limit} bytes"
