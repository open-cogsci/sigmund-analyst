from ..providers import jedi, codestral, ruff


def complete(code, cursor_pos, path, multiline, full):
    if full or multiline:
        completions = codestral.codestral_complete(
            code, cursor_pos, path=path, multiline=multiline)
    else:
        completions = []
    if not multiline:
        completions += jedi.jedi_complete(code, cursor_pos, path=path)
    return completions


calltip = jedi.jedi_signatures
check = ruff.ruff_check
symbols = jedi.jedi_symbols
