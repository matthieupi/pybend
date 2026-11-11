"""Protect static cascade priority and native file-containment boundaries.

Exercise the actual cascade and Starlette StaticFiles through an in-process
ASGI mount. Every asset, outside-root canary and symlink belongs to tmp_path.
No application factory, database, provider, remote HTTP or live file is used.
Linux symlink support is required; these cases deliberately do not skip.
Python has no block-comment syntax; the changelog uses native comments."""

from types import SimpleNamespace

import pytest
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.testclient import TestClient

from n3tx_core.api.backend import _CascadingStaticFiles


pytestmark = pytest.mark.unit


@pytest.fixture
def cascade(tmp_path, request):
    """Mount two actual static roots and retain decoded ASGI path evidence."""
    # 0. All three directories and their contents are disposable fixture data.
    ui = tmp_path / "ui"
    core = tmp_path / "core"
    outside = tmp_path / "outside"
    for directory in (ui, core, outside):
        directory.mkdir()
    handler = _CascadingStaticFiles(directories=[ui, core])
    observed = []

    async def mounted(scope, receive, send):
        """Record mount normalization without replacing native file lookup."""
        observed.append({
            "path": scope["path"], "root_path": scope.get("root_path", ""),
            "raw_path": scope.get("raw_path", b""),
        })
        await handler(scope, receive, send)

    prefix = getattr(request, "param", "")
    app = Starlette(routes=[Mount(prefix or "/", app=mounted)])
    # 1. TestClient is an ASGI transport, not a listener or remote HTTP client.
    with TestClient(app, raise_server_exceptions=False) as client:
        yield SimpleNamespace(
            ui=ui, core=core, outside=outside,
            client=client, observed=observed,
        )


def test_regular_override_keeps_priority_mime_and_conditional_semantics(
    cascade,
):
    """The first valid file owns GET, HEAD, MIME and conditional responses."""
    # 0. Both roots contain the same logical asset with different content.
    preferred = b"/* preferred UI override */\n"
    (cascade.ui / "shared.css").write_bytes(preferred)
    (cascade.core / "shared.css").write_bytes(b"/* later core copy */\n")
    # 1. A mounted request must retain native path and file-response behavior.
    response = cascade.client.get("/shared.css")
    assert response.status_code == 200
    assert response.content == preferred
    assert response.headers["content-type"].split(";")[0] == "text/css"
    assert int(response.headers["content-length"]) == len(preferred)
    head = cascade.client.head("/shared.css")
    assert head.status_code == 200 and head.content == b""
    for header in ("content-type", "content-length", "etag", "last-modified"):
        assert head.headers[header] == response.headers[header]
    # 2. A first-root 304 must not fall through to the later core copy.
    conditional = cascade.client.get("/shared.css", headers={
        "If-None-Match": response.headers["etag"],
    })
    assert conditional.status_code == 304
    assert conditional.content == b""
    assert conditional.headers["etag"] == response.headers["etag"]


def test_outside_root_symlink_without_later_copy_is_not_served(cascade):
    """Keep existing outside files private behind escaping symlinks."""
    # 0. The canary exists, so rejection must come from containment, not ENOENT.
    private = b"PRIVATE_OUTSIDE_CASCADE_CANARY"
    secret = cascade.outside / "secret.css"
    secret.write_bytes(private)
    (cascade.ui / "exposed.css").symlink_to(secret)
    # 1. Never enable follow_symlink merely to make an existing target readable.
    response = cascade.client.get("/exposed.css")
    assert response.status_code == 404
    assert private not in response.content


def test_rejected_ui_symlink_falls_through_to_regular_core_file(cascade):
    """A UI link outside its root must not mask an allowed core-root asset."""
    # 0. Reproduce the split-package link to an existing later-root core file.
    content = b"/* real core resource */\n"
    core_file = cascade.core / "shared.css"
    core_file.write_bytes(content)
    (cascade.ui / "shared.css").symlink_to(core_file)
    # 1. Native first-root rejection must permit the later valid regular file.
    response = cascade.client.get("/shared.css")
    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"].split(";")[0] == "text/css"


def test_symlink_resolving_within_first_root_remains_valid(cascade):
    """Permit symlinks whose resolved targets remain within the root."""
    # 0. An in-root link remains a valid first-root override of a later copy.
    nested = cascade.ui / "nested"
    nested.mkdir()
    preferred = b"/* contained UI target */\n"
    target = nested / "original.css"
    target.write_bytes(preferred)
    (cascade.ui / "alias.css").symlink_to(target)
    (cascade.core / "alias.css").write_bytes(b"/* not selected */\n")
    # 1. Containment is not a blanket symlink ban.
    response = cascade.client.get("/alias.css")
    assert response.status_code == 200
    assert response.content == preferred


@pytest.mark.parametrize("cascade", ["/assets"], indirect=True)
def test_encoded_traversal_reaches_asgi_but_cannot_escape_roots(cascade):
    """Block decoded traversal to existing files outside either root."""
    # 0. Percent encoding prevents client-side dot-segment URL normalization.
    private = b"PRIVATE_TRAVERSAL_CANARY"
    (cascade.outside / "secret.css").write_bytes(private)
    (cascade.ui / "nested").mkdir()
    preferred = b"/* normalized UI override */\n"
    (cascade.ui / "shared.css").write_bytes(preferred)
    (cascade.core / "shared.css").write_bytes(b"/* later core copy */\n")
    normalized = cascade.client.get("/assets/nested/%2e%2e/shared.css")
    assert normalized.status_code == 200
    assert normalized.content == preferred
    response = cascade.client.get("/assets/%2e%2e/outside/secret.css")
    # 1. Prove the mounted handler saw traversal, not an unrelated missing URL.
    observed = cascade.observed[-1]
    assert observed["root_path"] == "/assets"
    assert observed["path"].endswith("/../outside/secret.css")
    assert b"%2e%2e" in observed["raw_path"].lower()
    assert response.status_code == 404
    assert private not in response.content


def test_missing_asset_keeps_native_get_and_head_404(cascade):
    """Missing files retain native 404 status and HEAD's empty body."""
    # 0. Neither root contains this asset; no response alias is installed.
    response = cascade.client.get("/missing.css")
    head = cascade.client.head("/missing.css")
    # 1. Missing GET and HEAD must never become empty successful responses.
    assert response.status_code == head.status_code == 404
    assert head.content == b""


@pytest.mark.parametrize("status", [403, 500])
def test_selected_root_errors_are_not_hidden_by_later_copy(
    cascade, monkeypatch, status,
):
    """Propagate selected-root errors without serving a later root."""
    # 0. Both real lookups are valid; inject only response-generation failure.
    (cascade.ui / "shared.css").write_bytes(b"/* selected first */\n")
    later = b"/* fallback must not hide an error */\n"
    (cascade.core / "shared.css").write_bytes(later)
    native_response = StaticFiles.get_response

    async def fail_selected(self, path, scope):
        """Fail only the first root without mocking lookup or containment."""
        if str(self.directory) == str(cascade.ui):
            raise HTTPException(status, detail="selected static failure")
        return await native_response(self, path, scope)

    monkeypatch.setattr(StaticFiles, "get_response", fail_selected)
    # 1. Arbitrary 403/500 must propagate rather than become success or 404.
    response = cascade.client.get("/shared.css")
    assert response.status_code == status
    assert response.text == "selected static failure"
    assert later not in response.content


# Changelog (Python has no block-comment syntax).
# - 2026-11-10: Protect native cascade selection, containment and symlink
#   fallback with real temporary files; retain mounted-path, MIME, GET/HEAD,
#   conditional304, missing404 and non-swallowed selected-root error semantics.
