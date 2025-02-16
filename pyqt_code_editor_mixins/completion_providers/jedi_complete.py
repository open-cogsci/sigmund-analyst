import re
import logging
import jedi
from . import settings

logger = logging.getLogger(__name__)


def _prepare_jedi_script(code: str, cursor_position: int, path: str | None):
    """
    Prepare a Jedi Script object and calculate line_no/column_no from the
    given code and cursor_position. Returns (script, line_no, column_no).
    """
    # Convert the flat cursor_position into line & column (1-based indexing for Jedi)
    line_no = code[:cursor_position].count('\n') + 1
    last_newline_idx = code.rfind('\n', 0, cursor_position)
    if last_newline_idx < 0:
        column_no = cursor_position
    else:
        column_no = cursor_position - (last_newline_idx + 1)

    logger.info("Creating Jedi Script for path=%r at line=%d, column=%d",
             path, line_no, column_no)

    script = jedi.Script(code, path=path)
    return script, line_no, column_no


def jedi_complete(code: str, cursor_position: int, path: str | None, multiline: bool = False) -> list[str]:
    """
    Perform Python-specific completion using Jedi. Returns a list of possible completions
    for the text at the given cursor position, or None if no completion is found.
    """
    if cursor_position == 0 or not code:
        logger.info("No code or cursor_position=0; returning None.")
        return None

    # Basic sanity check for whether we want to attempt completion.
    char_before = code[cursor_position - 1]
    # Typically, you'd allow '.', '_' or alphanumeric as a signal for completion
    if not re.match(r"[A-Za-z0-9_.]", char_before):
        logger.info("Character before cursor is %r, not a valid trigger for completion.", char_before)
        return None

    logger.info("Starting Jedi completion request (multiline=%r).", multiline)
    script, line_no, column_no = _prepare_jedi_script(code, cursor_position, path)

    completions = script.complete(line=line_no, column=column_no)
    if not completions:
        logger.info("No completions returned by Jedi.")
        return None

    # Filter out "empty" completions
    result = [c.complete for c in completions[:settings.max_completions] if c.complete]
    logger.info("Got %d completion(s) from Jedi.", len(result))
    return result or None


def jedi_signatures(code: str, cursor_position: int, path: str | None, multiline: bool = False):
    """
    Retrieve function signatures (calltips) from Jedi given the current cursor position.
    Returns a list of strings describing each signature, or None if none.
    """
    if cursor_position == 0 or not code:
        logger.info("No code or cursor_position=0; cannot fetch calltip.")
        return None

    logger.info("Starting Jedi calltip request (multiline=%r).", multiline)
    script, line_no, column_no = _prepare_jedi_script(code, cursor_position, path)

    signatures = script.get_signatures(line=line_no, column=column_no)
    if not signatures:
        logger.info("No signatures returned by Jedi.")
        return None

    results = []
    for sig in signatures:
        # sig.to_string() often returns a signature like "function(param, param2)"
        sig_str = sig.to_string()
        # docstring() returns the doc if available
        doc_str = sig.docstring()
        # Combine them or pick what you need
        combined = f"{sig_str}\n\n{doc_str}".strip()
        results.append(combined)

    logger.info("Got %d signature(s) from Jedi.", len(results))
    return results or None
