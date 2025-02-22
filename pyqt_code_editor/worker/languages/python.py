from ..providers import jedi, codestral, ruff


def complete(code, cursor_pos, path, multiline):
    completions = jedi.jedi_complete(
        code, cursor_pos, path=path, multiline=multiline)
    if not completions:
        codestral.last_codestral_request_cursor = None
    completions = codestral.codestral_complete(
        code, cursor_pos, path=path, multiline=multiline) \
            + completions
    return completions


calltip = jedi.jedi_signatures
check = ruff.ruff_check
symbols = jedi.jedi_symbols
