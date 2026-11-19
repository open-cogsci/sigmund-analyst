"""In-process MCP filesystem server for the Sigmund MCP relay.

This is the in-process counterpart of the classic STDio
``@modelcontextprotocol/server-filesystem``: the same tools, but running
inside the IDE process on in-memory streams (one instance per relay
session) instead of as an ``npx`` subprocess.
"""
import os
import json
import shutil
import stat
import tempfile
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
import fnmatch
import difflib
import logging

from mcp_relay.agent import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

logger = logging.getLogger(__name__)

# Bound on the recursive walks, mirroring the reference
# ``@modelcontextprotocol/server-filesystem`` (its filesystem.md, "Slow and
# very large trees"): search_files and directory_tree visit at most this many
# entries, and a walk that reaches the cap ends with an error rather than a
# partial result. Excluded entries do not count.
MAX_VISITED_ENTRIES = 100_000


def expand_home(filepath: str) -> str:
    """Expand ~ to home directory"""
    if filepath == '~':
        return os.path.expanduser('~')
    elif filepath.startswith('~/'):
        return os.path.join(os.path.expanduser('~'), filepath[2:])
    return filepath


def normalize_path(p: str) -> str:
    """Normalize path consistently"""
    return os.path.normpath(p)


def is_within_allowed(path: str, allowed: list[str]) -> bool:
    """Check whether a path is an allowed directory itself or a descendant of one.

    Compares on path-component boundaries rather than by string prefix, so a
    sibling directory such as /home/u/project-backup is not treated as being
    inside the allowed directory /home/u/project.

    Args:
        path (str): Absolute, normalized path to test
        allowed (list[str]): Absolute, normalized allowed directories

    Returns:
        bool: True if path is contained in one of the allowed directories
    """
    candidate = Path(path)
    return any(candidate.is_relative_to(Path(d)) for d in allowed)


def canonical_path(p: str) -> str:
    """Resolve a path to the canonical form used for containment checks.

    Expands ~, makes the path absolute, then resolves symlinks and Windows 8.3
    short names via realpath. Allowed directories and requested paths are both
    reduced to this form, so a comparison cannot be defeated, or wrongly
    refused, by two different spellings of the same location.

    Args:
        p (str): Path to canonicalize

    Returns:
        str: Absolute, symlink-resolved, normalized path
    """
    return normalize_path(os.path.realpath(os.path.abspath(expand_home(p))))


def validate_allowed_directories(allowed_directories: list[str]) -> None:
    """Check that every allowed directory exists and is a directory.

    Raises:
        ValueError: If a directory does not exist or is not a directory
    """
    for dir_arg in allowed_directories:
        expanded_dir = expand_home(dir_arg)
        if not os.path.exists(expanded_dir):
            raise ValueError(f"Directory {dir_arg} does not exist")
        if not os.path.isdir(expanded_dir):
            raise ValueError(f"{dir_arg} is not a directory")


@dataclass
class FileInfo:
    size: int
    created: datetime
    modified: datetime
    accessed: datetime
    is_directory: bool
    is_file: bool
    permissions: str


@dataclass
class TreeEntry:
    name: str
    type: str  # 'file' or 'directory'
    children: list['TreeEntry'] | None = None


@dataclass
class EditOperation:
    old_text: str
    new_text: str


def validate_path(requested_path: str, allowed_directories: list[str]) -> str:
    """Validate that a path is within allowed directories

    The path is resolved to its canonical form before the containment check,
    so symlinks, Windows 8.3 short names and other aliases collapse to a
    single representation. allowed_directories is canonicalized the same way,
    keeping both sides of the comparison in the same form: an alias can
    neither be used to escape the allowed tree, nor cause a legitimate path
    inside it to be rejected.

    Args:
        requested_path (str): Path to validate
        allowed_directories (list[str]): Canonicalized allowed directories

    Returns:
        str: The validated, fully resolved path

    Raises:
        ToolError: If the path resolves outside every allowed directory
    """
    absolute = os.path.abspath(expand_home(requested_path))

    # realpath resolves symlinks and short names. Its default strict=False also
    # covers files that do not exist yet: the existing parent is resolved and
    # the remainder appended, so new-file targets are checked correctly.
    real_path = os.path.realpath(absolute)

    if not is_within_allowed(normalize_path(real_path), allowed_directories):
        raise ToolError(
            f"Access denied - path outside allowed directories: {absolute} "
            f"not in {', '.join(allowed_directories)}"
        )

    return real_path


def normalize_line_endings(text: str) -> str:
    """Normalize line endings to \\n"""
    return text.replace('\r\n', '\n')


def create_unified_diff(original_content: str, new_content: str, filepath: str = 'file') -> str:
    """Create a unified diff between two strings

    Args:
        original_content (str): Original string to diff against
        new_content (str): New string to diff
        filepath (str, optional): File path for diff header. Defaults to 'file'.

    Returns:
        str: Unified diff string
    """
    normalized_original = normalize_line_endings(original_content)
    normalized_new = normalize_line_endings(new_content)

    diff = difflib.unified_diff(
        normalized_original.splitlines(keepends=True),
        normalized_new.splitlines(keepends=True),
        fromfile=f"{filepath} (original)",
        tofile=f"{filepath} (modified)",
        lineterm=''
    )

    return ''.join(diff)


def apply_file_edits(file_path: str, edits: list[EditOperation], dry_run: bool = False) -> str:
    """Apply edits to a file and return diff

    Anchors that cannot identify exactly one location are refused rather than
    guessed at: empty or whitespace-only oldText cannot say where a change
    belongs, and a match on several locations when whitespace is ignored is
    ambiguous, so both raise ToolError (the latter naming the offending line
    numbers). If the combined edits leave the content as it was, that is
    reported and the file is left untouched. Otherwise the new content is
    written atomically: to a temporary file in the same directory that is
    then swapped over the target, so a crash mid-write cannot leave a
    truncated file behind.

    Args:
        file_path (str): Path to file to edit
        edits (list[EditOperation]): List of edit operations to apply
        dry_run (bool, optional): Whether to apply edits or not. Defaults to False.

    Returns:
        str: Unified diff string, or a message when nothing changed

    Raises:
        ToolError: If oldText is empty or whitespace-only, cannot be found,
            or matches more than one location when whitespace is ignored
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = normalize_line_endings(f.read())

    modified_content = content
    for edit in edits:
        normalized_old = normalize_line_endings(edit.old_text)
        normalized_new = normalize_line_endings(edit.new_text)

        # An empty or whitespace-only anchor cannot say where a change
        # belongs: an exact '' in text is always True (which would insert at
        # position 0), and a match this short bites on that many blank lines
        # anywhere in the file. Both are silent corruption, so refuse the
        # edit instead of guessing.
        if not normalized_old.strip():
            raise ToolError(
                "Could not apply edit: oldText is empty or whitespace-only, so "
                "it does not say where the change belongs. Provide the lines "
                "to change, with surrounding context, in oldText."
            )

        if normalized_old in modified_content:
            modified_content = modified_content.replace(normalized_old, normalized_new, 1)
            continue

        # Otherwise, try line-by-line matching with flexibility for whitespace.
        # Collect every window that matches before applying any of them, so
        # that ambiguity can be refused with the actual line numbers rather
        # than settled by whichever window happened to come first.
        old_lines = normalized_old.split('\n')
        content_lines = modified_content.split('\n')

        match_indices = [
            i for i in range(len(content_lines) - len(old_lines) + 1)
            if all(old.strip() == existing.strip()
                   for old, existing in zip(old_lines, content_lines[i:i + len(old_lines)]))
        ]

        if not match_indices:
            raise ToolError(f"Could not find exact match for edit:\n{edit.old_text}")

        if len(match_indices) > 1:
            # 1-based line numbers, on the content including earlier edits.
            locations = ', '.join(str(i + 1) for i in match_indices[:3])
            if len(match_indices) > 3:
                locations += ', ...'
            raise ToolError(
                f"Ambiguous edit: oldText matches {len(match_indices)} locations "
                f"(starting at lines {locations}) when whitespace is ignored, so "
                "the edit cannot be applied safely. Add surrounding context lines "
                "to oldText to make the match unique, or copy the text byte-for-byte."
            )

        i = match_indices[0]
        original_indent = content_lines[i][:len(content_lines[i]) - len(content_lines[i].lstrip())]

        new_lines = normalized_new.split('\n')
        for j, line in enumerate(new_lines):
            if j == 0:
                new_lines[j] = original_indent + line.lstrip()
            elif j < len(old_lines):
                # For subsequent lines, try to preserve relative indentation
                old_indent = old_lines[j][:len(old_lines[j]) - len(old_lines[j].lstrip())]
                new_indent = line[:len(line) - len(line.lstrip())]
                if old_indent and new_indent:
                    relative_indent = len(new_indent) - len(old_indent)
                    new_lines[j] = original_indent + ' ' * max(0, relative_indent) + line.lstrip()

        content_lines[i:i + len(old_lines)] = new_lines
        modified_content = '\n'.join(content_lines)

    # Nothing changed: report that instead of writing out an empty diff, and
    # leave the file alone, so that an identical oldText/newText edit does not
    # touch the file (or renormalize its line endings) for nothing.
    if modified_content == content:
        return ("Every edit in this batch matched, but oldText and newText were "
                "identical, so the file was left untouched.")

    diff = create_unified_diff(content, modified_content, file_path)

    num_backticks = 3
    while '`' * num_backticks in diff:
        num_backticks += 1
    formatted_diff = f"{'`' * num_backticks}diff\n{diff}{'`' * num_backticks}\n\n"

    if not dry_run:
        # Write atomically, not in place: open(..., 'w') truncates the file
        # first, so a crash mid-write would leave a truncated file behind.
        # Instead the new content goes to a temporary file in the same directory,
        # and os.replace swaps it in in one step: on the same filesystem that
        # leaves either the intact original or the complete new file, never a
        # torn half-written state.
        temp_fd, temp_path = tempfile.mkstemp(
            dir=os.path.dirname(file_path),
            prefix=f"{os.path.basename(file_path)}.",
            suffix='.tmp',
        )
        try:
            with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
                f.write(modified_content)
                f.flush()
                os.fsync(f.fileno())

            # mkstemp creates the temporary file with mode 0600; carry the
            # original mode over so swapping the file in does not change
            # its permissions.
            os.chmod(temp_path, stat.S_IMODE(os.stat(file_path).st_mode))
            os.replace(temp_path, file_path)
        except BaseException:
            # Always remove the temporary file -- also when cancelled -- so a
            # failed edit never leaves a stray *.tmp next to the target.
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise

    return formatted_diff


def read_text_file(valid_path: str) -> str:
    """Read a validated path as UTF-8 text.

    Files that are not valid UTF-8, such as binaries, are reported as an
    error rather than returned as mojibake.
    """
    try:
        with open(valid_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError as e:
        raise ToolError(
            f"Cannot read {valid_path} as UTF-8 text ({e.reason} at byte {e.start}). "
            "This tool reads text files only."
        ) from e


def get_file_stats(file_path: str) -> FileInfo:
    """Get detailed file statistics

    Args:
        file_path (str): Path to file to get stats for

    Returns:
        FileInfo: Detailed file statistics
    """
    stat = os.stat(file_path)
    return FileInfo(
        size=stat.st_size,
        created=datetime.fromtimestamp(stat.st_ctime),
        modified=datetime.fromtimestamp(stat.st_mtime),
        accessed=datetime.fromtimestamp(stat.st_atime),
        is_directory=os.path.isdir(file_path),
        is_file=os.path.isfile(file_path),
        permissions=oct(stat.st_mode)[-3:]
    )


def _is_excluded(relative_path: str, exclude_patterns: list[str]) -> bool:
    """Check whether a path relative to the search root matches an exclude pattern.

    A pattern without a wildcard matches that name at any depth, so
    ``node_modules`` excludes every ``node_modules`` directory and everything
    below it — including at the top level. Matching is done segment by segment
    rather than with ``fnmatch`` because ``**/name/**`` never matches a
    top-level ``name`` (``fnmatch`` requires a ``/`` before ``name``).

    A pattern with a wildcard is an ``fnmatch`` glob, matched against the
    relative path as written. ``fnmatch``'s '*' already crosses '/', so a glob
    matches at any depth. Both shorthands also reach the entries they name:
    stripping a leading '**/' lets '**/x' match a top-level 'x', and stripping
    a trailing '/**' lets 'x/**' match 'x' itself — so a glob ending in '/**'
    also excludes the directory it names, and that directory is then not
    listed, even as empty, and is never read.
    """
    for pattern in exclude_patterns:
        if '*' in pattern:
            # fnmatch's '*' already crosses '/', so a glob matches at any
            # depth, independent of the directory structure. Strip the two
            # shorthands as well so the glob also covers the entries they
            # name, and not only what follows them: '**/x', 'x/**' and
            # '**/x/**' should all also match a top-level 'x'.
            candidates = [pattern]
            if pattern.startswith('**/'):
                candidates.append(pattern[3:])
            if pattern.endswith('/**'):
                candidates.append(pattern[:-3])
                if pattern.startswith('**/'):
                    candidates.append(pattern[3:-3])
            if any(fnmatch.fnmatch(relative_path, c) for c in candidates):
                return True
        elif pattern in relative_path.split(os.sep):
            return True
    return False


def search_files_impl(root_path: str, pattern: str, allowed_directories: list[str],
                      exclude_patterns: list[str] | None = None) -> list[str]:
    """Recursively search for files matching a pattern

    The walk is bounded the way the reference server bounds it: at most
    ``MAX_VISITED_ENTRIES`` entries are visited, and a walk that reaches the
    cap ends with ToolError rather than a partial result. Excluded entries do
    not count.

    Args:
        root_path (str): Root directory to search in
        pattern (str): Glob pattern to match
        allowed_directories (list[str]): Canonicalized allowed directories
        exclude_patterns (list[str] | None, optional): Glob patterns to exclude. Defaults to None.

    Returns:
        list[str]: List of matching file paths

    Raises:
        ToolError: If the walk visits more than ``MAX_VISITED_ENTRIES`` entries
    """
    if exclude_patterns is None:
        exclude_patterns = []

    results = []
    visited_entries = 0

    for root, dirs, files in os.walk(root_path):
        relative_root = os.path.relpath(root, root_path)

        if _is_excluded(relative_root, exclude_patterns):
            dirs.clear()  # Don't recurse into excluded directories
            continue

        for item in dirs + files:
            full_path = os.path.join(root, item)

            # Defensive: skip anything that resolves outside the allowed roots
            # (e.g. reached through a symlink created during the walk).
            if not is_within_allowed(normalize_path(os.path.realpath(full_path)), allowed_directories):
                continue

            relative_path = os.path.relpath(full_path, root_path)
            if _is_excluded(relative_path, exclude_patterns):
                continue  # Excluded entries are not counted

            visited_entries += 1
            if visited_entries > MAX_VISITED_ENTRIES:
                raise ToolError(
                    f"File search of {root_path}: stopped after visiting "
                    f"{MAX_VISITED_ENTRIES} entries. Narrow the path, or name "
                    "the large folder in exclude_patterns."
                )

            if pattern.lower() in item.lower():
                results.append(full_path)

    return results


def build_directory_tree(current_path: str, allowed_directories: list[str],
                         exclude_patterns: list[str] | None = None,
                         depth: int | None = None) -> list[TreeEntry]:
    """Build a recursive tree structure of directories and files

    Bounded the way the reference ``@modelcontextprotocol/server-filesystem``
    bounds it: the walk visits at most ``MAX_VISITED_ENTRIES`` entries, and once
    the cap is reached the call fails with ToolError rather than descending
    into a partial (or enormous) result. Excluded entries do not count, and a
    depth limit keeps the walk out of deeper levels entirely, so entries below
    it do not count either.

    os.path.isdir follows symlinks, so a link pointing at one of its own
    ancestors would otherwise recurse until the stack is exhausted. Directories
    already expanded on the current descent are tracked by resolved path and
    reported without children instead of being walked again.

    Args:
        current_path (str): Current directory to build tree from
        allowed_directories (list[str]): Canonicalized allowed directories
        exclude_patterns (list[str] | None): Entries to leave out, read the
            same way as search_files's: a bare name excludes that name at any
            depth and the subtree below it, and a pattern containing * is a glob
            matched against the path written relative to the root. A glob ending
            in /** also excludes the directory it names, so it is not listed,
            even as empty, and is never read.
        depth (int | None): How many levels to descend: 1 lists only the
            entries directly in current_path, 2 adds their children, and so on;
            None walks the whole tree. Directories at the last level get no
            children, and their contents are never read.

    Returns:
        list[TreeEntry]: List of TreeEntry objects representing directories and files

    Raises:
        ToolError: If depth is given but is not a positive integer, or the
            walk visits more than MAX_VISITED_ENTRIES entries
    """
    if depth is not None and depth < 1:
        raise ToolError(f"depth must be a positive integer, not {depth}")

    root_path = validate_path(current_path, allowed_directories)

    # Resolved directories already expanded on this descent, used to break
    # symlink cycles.
    visited_directories: set[str] = set()
    # Entries visited so far, shared across the whole walk.
    visited_entries = 0

    def walk(directory_path: str, remaining_depth: int | None) -> list[TreeEntry]:
        nonlocal visited_entries

        valid_path = validate_path(directory_path, allowed_directories)

        resolved = normalize_path(os.path.realpath(valid_path))
        if resolved in visited_directories:
            return []
        visited_directories.add(resolved)

        entries = []

        try:
            for item in os.listdir(valid_path):
                item_path = os.path.join(valid_path, item)

                if exclude_patterns and _is_excluded(
                        os.path.relpath(item_path, root_path), exclude_patterns):
                    # Excluded: not listed, not read (not even as empty), and
                    # not counted toward the entry cap.
                    continue

                visited_entries += 1
                if visited_entries > MAX_VISITED_ENTRIES:
                    raise ToolError(
                        f"Directory tree of {current_path}: stopped after "
                        f"visiting {MAX_VISITED_ENTRIES} entries. Narrow the "
                        "path, or name the large folder in exclude_patterns."
                    )

                if os.path.isdir(item_path):
                    if remaining_depth is None or remaining_depth > 1:
                        children = walk(
                            item_path,
                            None if remaining_depth is None else remaining_depth - 1
                        )
                    else:
                        # Last level of a depth-limited walk: directories get
                        # no 'children', and their contents are never read.
                        children = None
                    entries.append(TreeEntry(
                        name=item,
                        type='directory',
                        children=children
                    ))
                else:
                    entries.append(TreeEntry(
                        name=item,
                        type='file'
                    ))
        except PermissionError:
            pass  # Skip directories we can't read

        return entries

    return walk(current_path, depth)


def make_mcp(allowed_roots: str | os.PathLike | list[str] | list[os.PathLike]) -> MCPServer:
    """Build an in-process MCP filesystem server restricted to allowed roots.

    Called once per relay session by ``InProcessServerProvider`` with the
    value returned by the provider's ``args_provider`` (typically the folder
    picked by the user). Returns a fresh ``MCPServer`` whose tools close over
    this session's allowed directories.

    Args:
        allowed_roots: A single root path, or a list of root paths, that the
            server is allowed to access

    Returns:
        MCPServer: A new in-process MCP server exposing the filesystem tools

    Raises:
        ValueError: If a root does not exist or is not a directory
    """
    if isinstance(allowed_roots, (str, os.PathLike)):
        allowed_roots = [allowed_roots]
    # Canonicalize the same way validate_path canonicalizes requested paths,
    # so both sides of the containment check share one representation.
    allowed_directories = [canonical_path(str(d)) for d in allowed_roots]
    validate_allowed_directories(allowed_directories)
    logger.info(f"In-process filesystem MCP server, allowed directories: {allowed_directories}")

    server = MCPServer("files")

    @server.tool()
    def read_file(path: str) -> str:
        """Read the complete contents of a file from the file system.

        Reads UTF-8 encoded text. Files that are not valid UTF-8, such as
        binaries, are reported as an error rather than returned as mojibake.
        Use this tool when you need to examine the contents of a single file.
        Only works within allowed directories.

        Args:
            path (str): Path to the file to read

        Returns:
            str: The contents of the file
        """
        logger.debug(f"read_file called with path: {path}")
        valid_path = validate_path(path, allowed_directories)
        logger.debug(f"Path validated: {valid_path}")
        content = read_text_file(valid_path)
        logger.debug(f"File read successfully, content length: {len(content)}")
        return content

    @server.tool()
    def read_multiple_files(paths: list[str]) -> str:
        """Read the contents of multiple files simultaneously.

        This is more efficient than reading files one by one when you need to analyze
        or compare multiple files. Each file's content is returned with its
        path as a reference. Failed reads for individual files won't stop
        the entire operation. Only works within allowed directories.

        Args:
            paths (list[str]): List of file paths to read

        Returns:
            str: A string containing the contents of each file, separated by "---".
        """
        results = []

        for file_path in paths:
            try:
                valid_path = validate_path(file_path, allowed_directories)
                content = read_text_file(valid_path)
                results.append(f"{file_path}:\n{content}\n")
            except Exception as e:
                results.append(f"{file_path}: Error - {str(e)}")

        return "\n---\n".join(results)

    @server.tool()
    def write_file(path: str, content: str) -> str:
        """Create a new file or completely overwrite an existing file with new content.

        Use with caution as it will overwrite existing files without warning.
        Handles text content with proper encoding. Only works within allowed directories.

        Args:
            path (str): Path to the file to write
            content (str): The content to write to the file

        Returns:
            str: A message indicating success
        """
        valid_path = validate_path(path, allowed_directories)

        os.makedirs(os.path.dirname(valid_path), exist_ok=True)

        with open(valid_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return f"Successfully wrote to {path}"

    @server.tool()
    def edit_file(path: str, edits: list[dict[str, str]], dry_run: bool = False) -> str:
        """Make line-based edits to a text file.

        Each edit replaces its oldText with newText: matching is exact first (with line
        endings normalized), falling back to a match whose lines need only equal each
        other once whitespace is stripped. An anchor that is empty or whitespace-only,
        that matches nothing, or that matches more than one location once whitespace is
        ignored is refused with an error rather than guessed at. Edits apply in order,
        and the file is rewritten atomically only after every edit in the batch has
        matched. Returns a git-style diff showing the changes made. Only works within
        allowed directories.

        Args:
            path: Path to the file to edit
            edits: List of edits, each containing 'oldText' and 'newText' keys
            dry_run: Preview changes using git-style diff format without applying them

        Returns:
            str: A git-style diff showing the changes made
        """
        valid_path = validate_path(path, allowed_directories)

        edit_operations = [
            EditOperation(old_text=edit['oldText'], new_text=edit['newText'])
            for edit in edits
        ]

        return apply_file_edits(valid_path, edit_operations, dry_run)

    @server.tool()
    def create_directory(path: str) -> str:
        """Create a new directory or ensure a directory exists.

        Can create multiple nested directories in one operation. If the directory already exists,
        this operation will succeed silently. Perfect for setting up directory
        structures for projects or ensuring required paths exist. Only works within allowed directories.

        Args:
            path (str): Path to the directory to create

        Returns:
            str: A message indicating success
        """
        valid_path = validate_path(path, allowed_directories)
        os.makedirs(valid_path, exist_ok=True)
        return f"Successfully created directory {path}"

    @server.tool()
    def list_directory(path: str) -> str:
        """Get a detailed listing of all files and directories in a specified path.

        Results clearly distinguish between files and directories with [FILE] and [DIR]
        prefixes. This tool is essential for understanding directory structure and
        finding specific files within a directory. Only works within allowed directories.

        Args:
            path (str): Path to the directory to list

        Returns:
            str: A newline-separated list of files and directories
        """
        valid_path = validate_path(path, allowed_directories)
        entries = []

        for item in os.listdir(valid_path):
            item_path = os.path.join(valid_path, item)
            if os.path.isdir(item_path):
                entries.append(f"[DIR] {item}")
            else:
                entries.append(f"[FILE] {item}")

        return "\n".join(entries)

    @server.tool()
    def directory_tree(path: str, exclude_patterns: list[str] | None = None,
                       depth: int | None = None) -> str:
        """Get a recursive tree view of files and directories as a JSON structure.

        Each entry includes 'name', 'type' ('file' or 'directory'), and, for a
        directory, 'children' with the entries it holds: an empty array for an
        empty directory, no children key for files, and no children key for
        directories at the last level when depth is set (they are not read, so
        whether they hold anything is not reported).

        The walk is bounded: at most 100,000 entries are visited, and a walk
        that reaches the cap ends with an error rather than a partial result.
        Excluded entries do not count, and a depth limit keeps the walk out of
        deeper levels entirely, so entries below it do not count either. If
        the cap is hit, narrow the path, or name the large folder in
        exclude_patterns.

        The output is formatted with 2-space indentation for readability.
        Only works within allowed directories.

        Args:
            path (str): Path to the directory to list
            exclude_patterns (list[str] | None): Entries to leave out, read the
                same way as search_files's: a bare name excludes that name at
                any depth and the subtree below it, and a pattern containing *
                is a glob matched against the path relative to path as
                written. A glob ending in /** also excludes the directory it
                names, so it is not listed, even as empty, and is never read.
            depth (int, optional): How many levels to descend: 1 lists only the
                entries directly in path, 2 adds their children, and so on.
                Omitted, the whole tree is returned.

        Returns:
            str: A JSON string representing the directory tree
        """
        tree_data = build_directory_tree(path, allowed_directories, exclude_patterns, depth)

        def tree_entry_to_dict(entry: TreeEntry) -> dict:
            result = {
                "name": entry.name,
                "type": entry.type
            }
            if entry.children is not None:
                result["children"] = [tree_entry_to_dict(child) for child in entry.children]
            return result

        tree_dict = [tree_entry_to_dict(entry) for entry in tree_data]
        return json.dumps(tree_dict, indent=2)

    @server.tool()
    def move_file(source: str, destination: str) -> str:
        """Move or rename files and directories.

        Can move files between directories and rename them in a single operation.
        If the destination exists, the operation will fail. Works across different directories
        and can be used for simple renaming within the same directory.
        Both source and destination must be within allowed directories.

        Args:
            source (str): Path to the file or directory to move
            destination (str): Path to the new location for the file or directory

        Returns:
            str: A message indicating success
        """
        valid_source_path = validate_path(source, allowed_directories)
        valid_dest_path = validate_path(destination, allowed_directories)

        # shutil.move replaces an existing file without warning, which contradicts
        # this tool's documented contract and would make the operation destructive.
        if os.path.exists(valid_dest_path):
            raise ToolError(f"Destination already exists, refusing to overwrite: {destination}")

        os.makedirs(os.path.dirname(valid_dest_path), exist_ok=True)

        shutil.move(valid_source_path, valid_dest_path)
        return f"Successfully moved {source} to {destination}"

    @server.tool()
    def search_files(path: str, pattern: str, exclude_patterns: list[str] | None = None) -> str:
        """Recursively search for files and directories matching a pattern.

        Searches through all subdirectories from the starting path. The search
        is case-insensitive and matches partial names. Returns full paths to all
        matching items. Great for finding files when you don't know their exact location.
        Only searches within allowed directories. The walk is bounded: at most
        100,000 entries are visited, and a walk that reaches the cap ends with
        an error rather than a partial result (excluded entries do not count).
        Narrow the path, or name the large folder in exclude_patterns.

        Args:
            path (str): Path to start the search from
            pattern (str): The search pattern to match
            exclude_patterns (list[str] | None): A list of patterns to exclude from the search

        Returns:
            str: A newline-separated list of matching file and directory paths
        """
        valid_path = validate_path(path, allowed_directories)
        results = search_files_impl(valid_path, pattern, allowed_directories, exclude_patterns)

        return "\n".join(results) if results else "No matches found"

    @server.tool()
    def get_file_info(path: str) -> str:
        """Retrieve detailed metadata about a file or directory.

        Returns comprehensive information including size, creation time, last modified time,
        permissions, and type. This tool is perfect for understanding file characteristics
        without reading the actual content. Only works within allowed directories.

        Args:
            path (str): Path to the file or directory to get information about

        Returns:
            str: A newline-separated list of file information
        """
        valid_path = validate_path(path, allowed_directories)
        info = get_file_stats(valid_path)

        return "\n".join([
            f"size: {info.size}",
            f"created: {info.created}",
            f"modified: {info.modified}",
            f"accessed: {info.accessed}",
            f"isDirectory: {info.is_directory}",
            f"isFile: {info.is_file}",
            f"permissions: {info.permissions}"
        ])

    @server.tool()
    def list_allowed_directories() -> str:
        """Returns the list of directories that this server is allowed to access.

        Use this to understand which directories are available before trying to access files.

        Returns:
            str: A newline-separated list of allowed directories
        """
        logger.debug("list_allowed_directories called")
        return f"Allowed directories:\n{chr(10).join(allowed_directories)}"

    logger.debug("All MCP tools registered successfully on in-process 'files' server")
    return server
