"""A fake api.github.com: commit lookups and tarballs, answered through httpx.MockTransport."""

import io
import tarfile
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class FakeRepo:
    """What the fake_repo fixture serves: question matches the one included file."""

    question: str


def tarball(files: dict[str, bytes], top: str = "o-r-abc") -> bytes:
    """A .tar.gz shaped like GitHub's, with every file under one top folder."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        folder = tarfile.TarInfo(top)
        folder.type = tarfile.DIRTYPE
        archive.addfile(folder)
        for path, content in files.items():
            info = tarfile.TarInfo(f"{top}/{path}")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))
    return buffer.getvalue()


def tarball_with_symlink(path: str, target: str = "../../etc/passwd") -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        link = tarfile.TarInfo(f"o-r-abc/{path}")
        link.type = tarfile.SYMTYPE
        link.linkname = target
        archive.addfile(link)
    return buffer.getvalue()


class FakeGitHub:
    """Serves repositories added with serve(). Fails the first fail_first requests with HTTP
    502, or every request with error=(status, headers)."""

    def __init__(self, fail_first: int = 0, error: tuple[int, dict[str, str]] | None = None):
        self.requests: list[httpx.Request] = []
        self._repositories: dict[tuple[str, str], tuple[str, bytes]] = {}
        self._fail_first = fail_first
        self._error = error

    def serve(self, repository: str, branch: str, sha: str, archive: bytes) -> None:
        self._repositories[(repository, branch)] = (sha, archive)

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self._handle))

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if len(self.requests) <= self._fail_first:
            return httpx.Response(502)
        if self._error is not None:
            status, headers = self._error
            return httpx.Response(status, headers=headers, json={"message": "error"})
        parts = request.url.path.strip("/").split("/")
        if request.url.host == "api.github.com" and len(parts) == 5 and parts[0] == "repos":
            repository, kind, ref = f"{parts[1]}/{parts[2]}", parts[3], parts[4]
            for (served, branch), (sha, _) in self._repositories.items():
                if served == repository and kind == "commits" and ref == branch:
                    return httpx.Response(200, text=sha)
                if served == repository and kind == "tarball" and ref == sha:
                    location = f"https://codeload.github.com/{repository}/legacy.tar.gz/{sha}"
                    return httpx.Response(302, headers={"Location": location})
        if request.url.host == "codeload.github.com":
            for (served, _), (sha, archive) in self._repositories.items():
                if request.url.path == f"/{served}/legacy.tar.gz/{sha}":
                    return httpx.Response(200, content=archive)
        return httpx.Response(404, json={"message": "Not Found"})
