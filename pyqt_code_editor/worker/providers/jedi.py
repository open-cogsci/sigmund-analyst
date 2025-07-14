import re
import logging
import jedi
from .. import settings

logger = logging.getLogger(__name__)


def _signature_to_html(signature) -> str:
    """Convert jedi.Script.get_signatures() output to nicely formatted HTML."""
    param_strs = []
    for param in signature.params:
        param_strs.append(param.to_string())
    # Build the signature line
    sig_line = ",<br />&nbsp;".join(param_strs)
    return_hint = ""
    # If there's a known return annotation, append it
    if hasattr(signature, "annotation_string") and signature.annotation_string:
        return_hint = f"-> {signature.annotation_string}"
    return f"({sig_line}){return_hint}"


def _prepare_jedi_script(code: str, cursor_position: int, path: str | None,
                         env_path: str | None):
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
    # We explicitly indicate that the environment is safe, because we know that
    # they come from the app itself
    env = jedi.create_environment(env_path, safe=False) if env_path else None
    script = jedi.Script(code, path=path, environment=env)
    return script, line_no, column_no


def jedi_complete(code: str, cursor_position: int, path: str | None,
                  env_path: str | None = None) -> list[str]:
    """
    Perform Python-specific completion using Jedi. Returns a list of possible completions
    for the text at the given cursor position, or None if no completion is found.
    """
    if cursor_position == 0 or not code:
        return []
    # Basic sanity check for whether we want to attempt completion.
    char_before = code[cursor_position - 1]
    # Typically, you'd allow '.', '_' or alphanumeric as a signal for completion
    if not re.match(r"[A-Za-z0-9_.]", char_before):
        return []
    # If the first preceding # comes before the first preceding newline, then we're inside a code comment
    code_up_to_cursor = code[:cursor_position]
    if code_up_to_cursor.rfind('#') > code_up_to_cursor.rfind('\n'):
        return []
    # Go Jedi!
    script, line_no, column_no = _prepare_jedi_script(code, cursor_position,
                                                      path, env_path)
    completions = script.complete(line=line_no, column=column_no)
    if not completions:
        return []
    result = [
        {'completion' : c.complete, 'name': c.name}
        for c in completions[:settings.max_completions] if c.complete
    ]
    return result or []


def jedi_signatures(code: str, cursor_position: int, path: str | None,
                    multiline: bool = False, max_width: int = 40,
                    max_lines: int = 10,
                    env_path: str | None = None):
    """
    Retrieve function signatures (calltips) from Jedi given the current cursor position.
    Returns a list of strings describing each signature, or None if none.

    Enhancements:
      1) If the docstring contains a duplicate of sig_str at the beginning, it's removed.
      2) The docstring is wrapped to max_width columns and truncated to max_lines lines.
    """
    if cursor_position == 0 or not code:
        logger.info("No code or cursor_position=0; cannot fetch calltip.")
        return None

    logger.info("Starting Jedi calltip request (multiline=%r).", multiline)
    script, line_no, column_no = _prepare_jedi_script(code, cursor_position,
                                                      path, env_path)

    signatures = script.get_signatures(line=line_no, column=column_no)
    if not signatures:
        logger.info("No signatures returned by Jedi.")
        return None

    results = []
    for sig in signatures:
        results.append(_signature_to_html(sig))

    logger.info("Got %d signature(s) from Jedi.", len(results))
    return results or None


def jedi_symbols(code: str) -> list[dict]:
    """Retrieve symbols from Jedi given the current code."""
    script = jedi.Script(code)
    symbols = script.get_names(all_scopes=True)
    results = []
    for symbol in symbols:
        if symbol.type not in ('function', 'class'):
            continue
        results.append({
            'name': symbol.name,
            'type': symbol.type,
            'line': symbol.line
        })
    return results
