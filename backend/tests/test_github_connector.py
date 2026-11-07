import httpx
import pytest

from app.ingestion.connectors.base import ConnectorError, FileTooLarge
from app.ingestion.connectors.github import (
    GitHubConnector,
    normalize_branch,
    normalize_repository,
)
from app.ingestion.connectors.globs import matches_include
from tests.github import FakeGitHub, tarball, tarball_with_symlink


@pytest.fixture
def connector(tmp_path):
    """A connector for o/r at branch main, including docs/**, served by a FakeGitHub."""

    def make(
        archive=None,
        *,
        status=200,
        headers=None,
        fail_first=0,
        max_file_bytes=1024,
        token=None,
        github=None,
    ):
        error = (status, headers or {}) if status != 200 else None
        github = github or FakeGitHub(fail_first=fail_first, error=error)
        if archive is not None:
            github.serve("o/r", "main", "abc", archive)
        return GitHubConnector(
            "o/r",
            "main",
            ["docs/**"],
            token,
            github.client(),
            max_file_bytes,
            temp_dir=tmp_path,
            retry_wait=0,
        )

    return make


@pytest.mark.parametrize(
    "value",
    [
        "kubernetes/website",
        "https://github.com/kubernetes/website",
        "https://github.com/kubernetes/website/",
        "https://github.com/kubernetes/website.git",
        "git@github.com:kubernetes/website.git",
        "  kubernetes/website  ",
    ],
)
def test_repository_forms_normalise(value):
    assert normalize_repository(value) == "kubernetes/website"


@pytest.mark.parametrize(
    "value", ["", "website", "https://example.com/a/b", "a/b/c", "o/..", "-o/r"]
)
def test_invalid_repository_is_rejected(value):
    with pytest.raises(ValueError):
        normalize_repository(value)


@pytest.mark.parametrize("value", ["main", " release/1.0 ", "feature/x-y_z"])
def test_valid_branch_names_are_kept(value):
    assert normalize_branch(value) == value.strip()


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "a..b",
        "a b",
        "/main",
        "main/",
        "-main",
        "a~1",
        "a^",
        "a:b",
        "x.lock",
        "a?b",
        "a*b",
        "a[b",
        "a\\b",
        "a@{b",
        "a//b",
    ],
)
def test_invalid_branch_is_rejected(value):
    with pytest.raises(ValueError):
        normalize_branch(value)


@pytest.mark.parametrize(
    "path, patterns, expected",
    [
        ("docs/a.md", ["docs/**"], True),
        ("docs/x/y/a.md", ["docs/**"], True),
        ("src/a.md", ["docs/**"], False),
        ("a.md", ["**"], True),
        ("docs/x/a.md", ["docs/*.md"], False),
        ("docs/a.md", ["docs/*.md"], True),
        ("docs/a.mdx", ["docs/*.md"], False),
        ("a.md", ["**/a.md"], True),
        ("x/y/a.md", ["**/a.md"], True),
        ("docs/ab.md", ["docs/a?.md"], True),
        ("docs/a/b.md", ["docs/a?b.md"], False),
        ("docs/x/a.md", ["docs/"], True),
        ("docs.md", ["docs/"], False),
        ("src/a.md", ["docs/**", "src/**"], True),
        ("docs+x/a.md", ["docs+x/**"], True),
    ],
)
def test_include_patterns(path, patterns, expected):
    assert matches_include(path, patterns) is expected


def test_lists_supported_matching_files_at_the_commit(connector):
    archive = tarball({"docs/a.md": b"x", "docs/b.png": b"x", "src/c.md": b"x"})
    items = list(connector(archive).list_items())
    assert [(i.path, i.revision) for i in items] == [("docs/a.md", "abc")]


def test_commit_is_resolved_as_a_bare_sha(connector):
    github = FakeGitHub()
    list(connector(tarball({"docs/a.md": b"x"}), github=github).list_items())
    first = github.requests[0]
    assert first.url.path == "/repos/o/r/commits/main"
    assert first.headers["accept"] == "application/vnd.github.sha"


def test_fetch_returns_the_file_content(connector):
    conn = connector(tarball({"docs/a.md": b"# A\nbody\n", "docs/b.md": b"# B\n"}))
    items = list(conn.list_items())
    assert [conn.fetch(item).content for item in items] == [b"# A\nbody\n", b"# B\n"]


def test_symlinks_are_skipped(connector):
    assert list(connector(tarball_with_symlink("docs/link.md")).list_items()) == []


def test_paths_leaving_the_repository_are_skipped(connector):
    archive = tarball({"docs/../../escape.md": b"x", "docs/a.md": b"x"})
    assert [i.path for i in connector(archive).list_items()] == ["docs/a.md"]


def test_oversized_file_raises_file_too_large(connector):
    conn = connector(tarball({"docs/a.md": b"x" * 11}), max_file_bytes=10)
    with pytest.raises(FileTooLarge):
        conn.fetch(next(iter(conn.list_items())))


def test_file_at_the_size_limit_is_fetched(connector):
    conn = connector(tarball({"docs/a.md": b"x" * 10}), max_file_bytes=10)
    assert conn.fetch(next(iter(conn.list_items()))).content == b"x" * 10


def test_unexpected_commit_id_is_rejected(connector):
    github = FakeGitHub()
    github.serve("o/r", "main", "../../x", tarball({"docs/a.md": b"x"}))
    with pytest.raises(ConnectorError, match="unexpected commit id"):
        list(connector(github=github).list_items())


def test_missing_repository_gives_a_clear_error(connector):
    with pytest.raises(ConnectorError, match="Repository not found or private"):
        list(connector(status=404).list_items())


def test_unknown_branch_gives_a_clear_error(connector):
    with pytest.raises(ConnectorError, match="Branch main not found"):
        list(connector(status=422).list_items())


def test_rejected_token_gives_a_clear_error(connector):
    with pytest.raises(ConnectorError, match="GITHUB_TOKEN"):
        list(connector(status=401).list_items())


@pytest.mark.parametrize(
    "status, headers",
    [(403, {"x-ratelimit-remaining": "0"}), (403, {"retry-after": "60"}), (429, {})],
)
def test_rate_limit_gives_a_clear_error(connector, status, headers):
    with pytest.raises(ConnectorError, match="GitHub rate limit"):
        list(connector(status=status, headers=headers).list_items())


def test_other_forbidden_responses_are_not_called_a_rate_limit(connector):
    with pytest.raises(ConnectorError) as caught:
        list(connector(status=403).list_items())
    assert "rate limit" not in str(caught.value)


def test_server_error_is_retried(connector):
    conn = connector(tarball({"docs/a.md": b"x"}), fail_first=2)
    assert len(list(conn.list_items())) == 1


def test_lasting_server_error_gives_a_clear_error(connector):
    with pytest.raises(ConnectorError, match="GitHub is unavailable"):
        list(connector(status=502).list_items())


def test_lost_connection_gives_a_clear_error(tmp_path):
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(refuse))
    conn = GitHubConnector("o/r", "main", ["**"], None, client, 10, temp_dir=tmp_path, retry_wait=0)
    with pytest.raises(ConnectorError, match="GitHub is unavailable"):
        list(conn.list_items())


def test_token_is_sent_as_a_bearer_token(connector):
    github = FakeGitHub()
    list(connector(tarball({"docs/a.md": b"x"}), token="t0ken", github=github).list_items())
    assert github.requests[0].headers["authorization"] == "Bearer t0ken"


def test_no_token_sends_no_authorization(connector):
    github = FakeGitHub()
    list(connector(tarball({"docs/a.md": b"x"}), github=github).list_items())
    assert "authorization" not in github.requests[0].headers


def test_archive_is_downloaded_into_the_configured_folder(connector, tmp_path):
    conn = connector(tarball({"docs/a.md": b"x"}))
    list(conn.list_items())
    assert conn.archive_path.parent == tmp_path


def test_temporary_archive_is_removed_on_close(connector):
    conn = connector(tarball({"docs/a.md": b"x"}))
    list(conn.list_items())
    archive = conn.archive_path
    conn.close()
    assert not archive.exists()


def test_corrupt_archive_gives_a_clear_error(connector):
    with pytest.raises(ConnectorError, match="archive"):
        list(connector(b"\x1f\x8b not really gzip").list_items())
