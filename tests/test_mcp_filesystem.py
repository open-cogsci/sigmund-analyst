"""Tests for the in-process filesystem MCP server
(pyqt_code_editor/components/sigmund_mcp_relay/servers/mcp_filesystem.py).

The server is exercised through ``MCPServer.call_tool`` — the same entry
point the MCP SDK uses when serving requests — plus one end-to-end test that
runs the server over in-memory streams with a real ``ClientSession``, the
same setup ``mcp_relay.agent.InProcessServerProvider`` uses in production.

Run from the repo root:

    python -m pytest tests/test_mcp_filesystem.py

``mcp_relay`` must be importable: it is a declared dependency
(``sigmund-mcp-relay``); in a source checkout the sibling repo also works via
PYTHONPATH, as run-dev.sh sets up.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # importing the package pulls in qtpy

try:
    import mcp_relay.agent  # noqa: F401
except ModuleNotFoundError:  # source checkout: fall back to the sibling repo
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mcp_relay"))

import anyio
from mcp.client.session import ClientSession
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from pyqt_code_editor.components.sigmund_mcp_relay.servers.mcp_filesystem import (
    _is_excluded,
    canonical_path,
    is_within_allowed,
    make_mcp,
    validate_path,
)

EXPECTED_TOOLS = {
    "read_file", "read_multiple_files", "write_file", "edit_file",
    "create_directory", "list_directory", "directory_tree", "move_file",
    "search_files", "get_file_info", "list_allowed_directories",
}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def call(server, name, arguments):
    """Call a tool the way the MCP server does; returns the CallToolResult."""
    return asyncio.run(server.call_tool(name, arguments))


def call_error(server, name, arguments):
    """Call a tool that is expected to fail; returns the raised ToolError."""
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(server.call_tool(name, arguments))
    return exc_info.value


def text(result):
    """The text content of a CallToolResult."""
    return result.content[0].text


def make_symlink(src, dst):
    try:
        os.symlink(src, dst)
    except OSError as e:
        pytest.skip(f"cannot create symlinks on this system: {e}")


# ---------------------------------------------------------------------------
# _is_excluded: exclude-pattern matching used by search_files
# ---------------------------------------------------------------------------

class TestIsExcluded:
    @pytest.mark.parametrize("relative_path", [
        "node_modules", "node_modules/pkg", "a/node_modules", "a/node_modules/pkg/index.js",
    ])
    def test_bare_name_matches_at_any_depth(self, relative_path):
        assert _is_excluded(relative_path, ["node_modules"])

    @pytest.mark.parametrize("relative_path", [
        "pkg/index.js", "sub/nested.py", "sub/node_modulesx", ".",
    ])
    def test_bare_name_does_not_partially_match(self, relative_path):
        assert not _is_excluded(relative_path, ["node_modules"])

    def test_glob_matches_at_any_depth(self):
        assert _is_excluded("sub/nested.py", ["*.py"])
        assert _is_excluded("x.py", ["*.py"])
        assert not _is_excluded("sub/x.txt", ["*.py"])

    def test_doublestar_glob_matches_top_level_too(self):
        assert _is_excluded("x.py", ["**/*.py"])
        assert _is_excluded("sub/nested.py", ["**/*.py"])

    def test_no_patterns(self):
        assert not _is_excluded("anything/at/all", [])


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def root(tmp_path):
    """An allowed root directory with a small file tree."""
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    (root / "empty_dir").mkdir()
    (root / "node_modules" / "pkg").mkdir(parents=True)
    (root / "hello.txt").write_text("hello world\n")
    (root / "binary.bin").write_bytes(bytes(range(256)))
    (root / "sub" / "nested.py").write_text("def f():\n    return 1\n")
    (root / "sub" / "another.txt").write_text("another\n")
    (root / "node_modules" / "pkg" / "index.js").write_text("console.log(1)\n")
    return root


@pytest.fixture
def server(root):
    return make_mcp(str(root))


# ---------------------------------------------------------------------------
# make_mcp: the per-session factory
# ---------------------------------------------------------------------------

class TestMakeMcp:
    def test_accepts_single_path_pathlike_and_list(self, root):
        for arg in (str(root), root, [str(root)], [root]):
            s = make_mcp(arg)
            out = text(call(s, "list_allowed_directories", {}))
            assert out == f"Allowed directories:\n{canonical_path(str(root))}"

    def test_rejects_missing_directory(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            make_mcp(str(tmp_path / "nope"))

    def test_rejects_file(self, root):
        with pytest.raises(ValueError, match="not a directory"):
            make_mcp(str(root / "hello.txt"))

    def test_root_is_canonicalized(self, root):
        # a root spelled with .. resolves to the same canonical directory
        s = make_mcp(os.path.join(str(root), "sub", ".."))
        assert canonical_path(str(root)) in text(call(s, "list_allowed_directories", {}))

    def test_sessions_are_isolated(self, tmp_path):
        """Each make_mcp() call gets its own allowed directories."""
        a, b = tmp_path / "a", tmp_path / "b"
        a.mkdir()
        b.mkdir()
        (a / "only_a.txt").write_text("A")
        (b / "only_b.txt").write_text("B")
        sa, sb = make_mcp(str(a)), make_mcp(str(b))
        assert "only_a" in text(call(sa, "search_files", {"path": str(a), "pattern": "only"}))
        assert "Access denied" in str(call_error(sb, "read_file", {"path": str(a / "only_a.txt")}))
        assert canonical_path(str(a)) in text(call(sa, "list_allowed_directories", {}))
        assert canonical_path(str(a)) not in text(call(sb, "list_allowed_directories", {}))


# ---------------------------------------------------------------------------
# tool registration and schemas
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_all_expected_tools_registered_with_descriptions(self, server):
        tools = asyncio.run(server.list_tools())
        assert {t.name for t in tools} == EXPECTED_TOOLS
        for t in tools:
            assert t.description and t.description.strip(), f"{t.name} has no description"

    def test_input_schemas(self, server):
        tools = {t.name: t for t in asyncio.run(server.list_tools())}
        assert tools["read_file"].input_schema["required"] == ["path"]
        search = tools["search_files"].input_schema
        assert search["required"] == ["path", "pattern"]
        assert "exclude_patterns" in search["properties"]  # optional
        edit = tools["edit_file"].input_schema
        assert edit["required"] == ["path", "edits"]
        assert edit["properties"]["dry_run"]["default"] is False
        assert tools["list_allowed_directories"].input_schema.get("properties", {}) == {}

    def test_unknown_tool(self, server):
        assert "Unknown tool" in str(call_error(server, "no_such_tool", {}))

    def test_invalid_arguments(self, server):
        err = call_error(server, "read_file", {"path": 123})
        assert "path" in str(err)


# ---------------------------------------------------------------------------
# path validation (the security boundary)
# ---------------------------------------------------------------------------

class TestPathValidation:
    def test_root_and_descendants_are_allowed(self, root):
        allowed = [canonical_path(str(root))]
        assert validate_path(str(root), allowed) == canonical_path(str(root))
        assert validate_path(str(root / "sub" / "nested.py"), allowed).endswith("nested.py")

    def test_sibling_with_common_prefix_is_rejected(self, tmp_path, root):
        """/tmp/.../root-backup must not count as inside /tmp/.../root."""
        backup = tmp_path / "root-backup"
        backup.mkdir()
        (backup / "secret.txt").write_text("secret")
        allowed = [canonical_path(str(root))]
        assert not is_within_allowed(canonical_path(str(backup)), allowed)
        with pytest.raises(ToolError, match="Access denied"):
            validate_path(str(backup / "secret.txt"), allowed)

    def test_dotdot_traversal_is_rejected(self, root):
        allowed = [canonical_path(str(root))]
        with pytest.raises(ToolError, match="Access denied"):
            validate_path(os.path.join(str(root), "..", "..", "etc", "passwd"), allowed)

    def test_symlink_escape_is_rejected(self, tmp_path, root):
        outside = tmp_path / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("secret")
        make_symlink(outside, root / "escape")
        allowed = [canonical_path(str(root))]
        with pytest.raises(ToolError, match="Access denied"):
            validate_path(str(root / "escape" / "secret.txt"), allowed)


# ---------------------------------------------------------------------------
# read_file / read_multiple_files
# ---------------------------------------------------------------------------

class TestReadFile:
    def test_reads_text_file(self, server, root):
        result = call(server, "read_file", {"path": str(root / "hello.txt")})
        assert text(result) == "hello world\n"
        assert result.structured_content == {"result": "hello world\n"}

    def test_denied_outside_root(self, server):
        assert "Access denied" in str(call_error(server, "read_file", {"path": "/etc/passwd"}))

    def test_symlink_escape_is_denied(self, server, root, tmp_path):
        (tmp_path / "outside.txt").write_text("secret")
        make_symlink(tmp_path, root / "escape")
        err = call_error(server, "read_file", {"path": str(root / "escape" / "outside.txt")})
        assert "Access denied" in str(err)

    def test_missing_file(self, server, root):
        # NOTE: currently surfaced as a generic unexpected error; a friendly
        # "file not found" ToolError would be nicer for the remote model.
        with pytest.raises(ToolError) as exc_info:
            asyncio.run(server.call_tool("read_file", {"path": str(root / "missing.txt")}))
        assert isinstance(exc_info.value, UnexpectedToolError)

    def test_binary_file_is_a_clean_error(self, server, root):
        err = call_error(server, "read_file", {"path": str(root / "binary.bin")})
        assert "UTF-8" in str(err)


class TestReadMultipleFiles:
    def test_ok_missing_and_denied_do_not_stop_each_other(self, server, root):
        result = text(call(server, "read_multiple_files", {"paths": [
            str(root / "hello.txt"),
            str(root / "missing.txt"),
            "/etc/passwd",
        ]}))
        parts = result.split("\n---\n")
        assert len(parts) == 3
        assert parts[0] == f"{root / 'hello.txt'}:\nhello world\n\n"
        assert "Error" in parts[1]
        assert "Access denied" in parts[2]


# ---------------------------------------------------------------------------
# write_file / edit_file
# ---------------------------------------------------------------------------

class TestWriteFile:
    def test_write_new_file_creates_parent_directories(self, server, root):
        target = root / "new" / "deep" / "file.txt"
        msg = text(call(server, "write_file", {"path": str(target), "content": "abc"}))
        assert "Successfully wrote" in msg
        assert target.read_text() == "abc"

    def test_overwrites_existing_file(self, server, root):
        f = root / "hello.txt"
        call(server, "write_file", {"path": str(f), "content": "bye"})
        assert f.read_text() == "bye"

    def test_denied_outside_root(self, server, tmp_path):
        target = tmp_path / "evil.txt"
        err = call_error(server, "write_file", {"path": str(target), "content": "x"})
        assert "Access denied" in str(err)
        assert not target.exists()


class TestEditFile:
    def test_exact_match_edit_returns_diff_and_writes(self, server, root):
        f = root / "sub" / "nested.py"
        res = text(call(server, "edit_file", {"path": str(f), "edits": [
            {"oldText": "return 1", "newText": "return 42"}]}))
        assert "```diff" in res
        assert "-    return 1" in res
        assert "+    return 42" in res
        assert f.read_text() == "def f():\n    return 42\n"

    def test_whitespace_flexible_match(self, server, root):
        f = root / "sub" / "nested.py"
        call(server, "edit_file", {"path": str(f), "edits": [
            {"oldText": "def f():\nreturn 1", "newText": "def f():\n    return 42"}]})
        assert f.read_text() == "def f():\n    return 42\n"

    def test_multiple_edits_applied_in_order(self, server, root):
        f = root / "hello.txt"
        call(server, "edit_file", {"path": str(f), "edits": [
            {"oldText": "hello", "newText": "goodbye"},
            {"oldText": "world", "newText": "moon"},
        ]})
        assert f.read_text() == "goodbye moon\n"

    def test_no_match_is_an_error_and_leaves_file_unchanged(self, server, root):
        f = root / "hello.txt"
        before = f.read_text()
        err = call_error(server, "edit_file", {"path": str(f), "edits": [
            {"oldText": "not there", "newText": "x"}]})
        assert "Could not find exact match" in str(err)
        assert f.read_text() == before

    def test_dry_run_returns_diff_but_does_not_write(self, server, root):
        f = root / "hello.txt"
        before = f.read_text()
        res = text(call(server, "edit_file", {"path": str(f), "dry_run": True,
                                              "edits": [{"oldText": "hello", "newText": "bye"}]}))
        assert "+bye" in res
        assert f.read_text() == before

    def test_crlf_line_endings_are_normalized(self, server, root):
        f = root / "crlf.txt"
        f.write_bytes(b"line1\r\nline2\r\n")
        call(server, "edit_file", {"path": str(f), "edits": [
            {"oldText": "line2", "newText": "LINE2"}]})
        assert f.read_text() == "line1\nLINE2\n"

    def test_denied_outside_root(self, server, tmp_path):
        f = tmp_path / "outside.txt"
        f.write_text("x")
        err = call_error(server, "edit_file", {"path": str(f), "edits": [
            {"oldText": "x", "newText": "y"}]})
        assert "Access denied" in str(err)
        assert f.read_text() == "x"


# ---------------------------------------------------------------------------
# directories: create_directory / list_directory / directory_tree
# ---------------------------------------------------------------------------

class TestDirectories:
    def test_create_nested_is_idempotent(self, server, root):
        d = root / "a" / "b" / "c"
        assert "Successfully created" in text(call(server, "create_directory", {"path": str(d)}))
        assert d.is_dir()
        call(server, "create_directory", {"path": str(d)})  # already exists: still fine
        assert d.is_dir()

    def test_create_denied_outside_root(self, server, tmp_path):
        err = call_error(server, "create_directory", {"path": str(tmp_path / "nope")})
        assert "Access denied" in str(err)

    def test_list_directory_marks_files_and_dirs(self, server, root):
        out = text(call(server, "list_directory", {"path": str(root)}))
        assert "[DIR] sub" in out
        assert "[FILE] hello.txt" in out

    def test_list_directory_denied_outside_root(self, server):
        assert "Access denied" in str(call_error(server, "list_directory", {"path": "/etc"}))

    def test_directory_tree_structure(self, server, root):
        tree = json.loads(text(call(server, "directory_tree", {"path": str(root)})))
        by_name = {e["name"]: e for e in tree}
        assert by_name["sub"]["type"] == "directory"
        assert {c["name"] for c in by_name["sub"]["children"]} == {"nested.py", "another.txt"}
        assert by_name["hello.txt"]["type"] == "file"
        assert "children" not in by_name["hello.txt"]

    def test_directory_tree_survives_symlink_cycle(self, server, root):
        make_symlink(root, root / "loop")  # loop points at its own parent
        tree = json.loads(text(call(server, "directory_tree", {"path": str(root)})))
        by_name = {e["name"]: e for e in tree}
        assert by_name["loop"]["children"] == []  # not followed, no infinite recursion


# ---------------------------------------------------------------------------
# move_file
# ---------------------------------------------------------------------------

class TestMoveFile:
    def test_move_file(self, server, root):
        src, dst = root / "hello.txt", root / "sub" / "moved.txt"
        assert "Successfully moved" in text(
            call(server, "move_file", {"source": str(src), "destination": str(dst)}))
        assert not src.exists()
        assert dst.read_text() == "hello world\n"

    def test_move_directory(self, server, root):
        src, dst = root / "sub", root / "renamed"
        call(server, "move_file", {"source": str(src), "destination": str(dst)})
        assert (dst / "nested.py").exists()
        assert not src.exists()

    def test_refuses_to_overwrite_existing_destination(self, server, root):
        src, dst = root / "hello.txt", root / "sub" / "another.txt"
        err = call_error(server, "move_file", {"source": str(src), "destination": str(dst)})
        assert "Destination already exists" in str(err)
        assert src.exists()
        assert dst.read_text() == "another\n"

    def test_denied_when_destination_is_outside_root(self, server, root, tmp_path):
        err = call_error(server, "move_file", {
            "source": str(root / "hello.txt"), "destination": str(tmp_path / "x.txt")})
        assert "Access denied" in str(err)
        assert (root / "hello.txt").exists()


# ---------------------------------------------------------------------------
# search_files
# ---------------------------------------------------------------------------

class TestSearchFiles:
    def test_case_insensitive_substring_match(self, server, root):
        out = text(call(server, "search_files", {"path": str(root), "pattern": "NESTED"}))
        assert out == str(root / "sub" / "nested.py")

    def test_exclude_patterns(self, server, root):
        found = text(call(server, "search_files", {"path": str(root), "pattern": "index"}))
        assert "index.js" in found
        excluded = text(call(server, "search_files", {
            "path": str(root), "pattern": "index", "exclude_patterns": ["node_modules"]}))
        assert excluded == "No matches found"

    def test_no_matches(self, server, root):
        out = text(call(server, "search_files", {"path": str(root), "pattern": "zzz-no-such-thing"}))
        assert out == "No matches found"

    def test_denied_outside_root(self, server):
        err = call_error(server, "search_files", {"path": "/etc", "pattern": "passwd"})
        assert "Access denied" in str(err)

    def test_symlinked_directory_is_not_followed(self, server, root, tmp_path):
        (tmp_path / "secret_outside.txt").write_text("x")
        make_symlink(tmp_path, root / "linkdir")
        out = text(call(server, "search_files", {"path": str(root), "pattern": "secret_outside"}))
        assert out == "No matches found"
        out = text(call(server, "search_files", {"path": str(root), "pattern": "linkdir"}))
        assert out == "No matches found"


# ---------------------------------------------------------------------------
# get_file_info / list_allowed_directories
# ---------------------------------------------------------------------------

class TestFileInfo:
    def test_file_info(self, server, root):
        out = text(call(server, "get_file_info", {"path": str(root / "hello.txt")}))
        assert "isFile: True" in out
        assert "isDirectory: False" in out
        assert f"size: {len('hello world\n')}" in out
        assert "permissions:" in out

    def test_directory_info(self, server, root):
        out = text(call(server, "get_file_info", {"path": str(root / "sub")}))
        assert "isDirectory: True" in out
        assert "isFile: False" in out

    def test_denied_outside_root(self, server):
        err = call_error(server, "get_file_info", {"path": "/etc"})
        assert "Access denied" in str(err)


def test_list_allowed_directories(server, root):
    out = text(call(server, "list_allowed_directories", {}))
    assert out == f"Allowed directories:\n{canonical_path(str(root))}"


# ---------------------------------------------------------------------------
# end-to-end: a real MCP session over in-memory streams
# ---------------------------------------------------------------------------

class TestMcpSession:
    def test_full_session_over_memory_streams(self, server, root):
        """Run the server the way InProcessServerProvider does: on memory
        streams, with a real MCP client session on the other end."""

        async def main():
            lowlevel = getattr(server, "_lowlevel_server", server)
            client_send, server_recv = anyio.create_memory_object_stream(100)
            server_send, client_recv = anyio.create_memory_object_stream(100)
            server_task = asyncio.create_task(lowlevel.run(
                server_recv, server_send, lowlevel.create_initialization_options()))
            try:
                async with ClientSession(client_recv, client_send) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert {t.name for t in tools.tools} == EXPECTED_TOOLS

                    ok = await session.call_tool("read_file", {"path": str(root / "hello.txt")})
                    assert not ok.is_error
                    assert ok.content[0].text == "hello world\n"

                    denied = await session.call_tool("read_file", {"path": "/etc/passwd"})
                    assert denied.is_error
                    assert "Access denied" in denied.content[0].text
            finally:
                await client_send.aclose()
                await asyncio.wait_for(server_task, 5)

        asyncio.run(main())
