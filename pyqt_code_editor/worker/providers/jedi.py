import re
import logging
import jedi
from .. import settings

logger = logging.getLogger(__name__)
env_cache = {}


def _estimate_width(text):
    """Helper function to estimate display width of signature
    (rough approximation)
    """
    # Remove HTML tags for width calculation
    clean_text = re.sub(r'<[^>]+>', '', text)
    return len(clean_text)


def _wrap_params(params, width_limit):
    """Helper function to wrap signature parameters"""
    lines = []
    current_line = []
    current_width = 1  # Starting with "("
    
    for i, param in enumerate(params):
        param_width = _estimate_width(param)
        # Add comma and space width for non-first parameters
        if current_line:
            param_width += 2
        
        # Check if adding this param would exceed width
        if current_line and current_width + param_width > width_limit:
            # Start a new line
            lines.append(", ".join(current_line))
            current_line = [param]
            current_width = 6 + param_width  # Indent width + param
        else:
            current_line.append(param)
            current_width += param_width
    
    if current_line:
        lines.append(", ".join(current_line))
    
    return lines


def _signature_to_html(signature, max_width: int, max_lines: int) -> str:
    """Convert jedi.Script.get_signatures() output to nicely formatted HTML."""
    param_strs = []
    for param in signature.params:
        param_strs.append(param.to_string())
    
    # Get return annotation if available
    return_hint = ""
    if hasattr(signature, "annotation_string") and signature.annotation_string:
        return_hint = f" -> {signature.annotation_string}"
    
    # Wrap parameters based on max_width
    wrapped_lines = _wrap_params(param_strs,
                                 max_width - _estimate_width(return_hint) - 2)
    
    # Limit number of lines
    if len(wrapped_lines) > max_lines:
        # Keep first max_lines-1 lines and add ellipsis
        wrapped_lines = wrapped_lines[:max_lines-1]
        if wrapped_lines:
            wrapped_lines[-1] += ", ..."
    
    # Build the final HTML
    if len(wrapped_lines) == 0:
        return f"(){return_hint}"
    elif len(wrapped_lines) == 1:
        return f"({wrapped_lines[0]}){return_hint}"
    else:
        # Multi-line format with indentation
        html_lines = [f"({wrapped_lines[0]},"]
        for line in wrapped_lines[1:-1]:
            html_lines.append(f"<br />&nbsp;{line},")
        html_lines.append(f"<br />&nbsp;{wrapped_lines[-1]}){return_hint}")
        return "".join(html_lines)


def _prepare_jedi_script(code: str, cursor_position: int, path: str | None,
                         env_path: str | None, prefix: str | None = None):
    """
    Prepare a Jedi Script object and calculate line_no/column_no from the
    given code and cursor_position. Returns (script, line_no, column_no).
    """
    if prefix:
        if not prefix.endswith('\n'):
            prefix += '\n'
        code = prefix + code
        cursor_position += len(prefix)
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
    if env_path not in env_cache:        
        env = jedi.create_environment(env_path, safe=False) if env_path else None
        env_cache[env_path] = env
    else:
        env = env_cache[env_path]
    script = jedi.Script(code, path=path, environment=env)
    return script, line_no, column_no


def jedi_complete(code: str, cursor_position: int, path: str | None,
                  env_path: str | None = None,
                  prefix: str | None = None) -> list[str]:
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
                                                      path, env_path, prefix)
    completions = script.complete(line=line_no, column=column_no)
    if not completions:
        return []
    result = [
        {'completion' : c.complete, 'name': c.name}
        for c in completions[:settings.max_completions] if c.complete
    ]
    return result or []


def jedi_signatures(code: str, cursor_position: int, path: str | None,
                    max_width: int = 40, max_lines: int = 10,
                    env_path: str | None = None,
                    prefix: str | None = None) -> list[str]:
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

    logger.info("Starting Jedi calltip request")
    script, line_no, column_no = _prepare_jedi_script(code, cursor_position,
                                                      path, env_path, prefix)

    signatures = script.get_signatures(line=line_no, column=column_no)
    if not signatures:
        logger.info("No signatures returned by Jedi.")
        return None

    results = []
    for sig in signatures:
        results.append(_signature_to_html(sig, max_width, max_lines))

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
