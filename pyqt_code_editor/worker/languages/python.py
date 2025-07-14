from ..providers import jedi, codestral, ruff


def complete(code, cursor_pos, path, multiline, full, env_path):
    if full or multiline:
        codestral_completions = codestral.codestral_complete(
            code, cursor_pos, multiline=multiline)
    else:
        codestral_completions = []
    if not multiline:
        jedi_completions = jedi.jedi_complete(code, cursor_pos, path=path,
                                              env_path=env_path)
    else:
        jedi_completions = []
    # If there is at least one jedi completion, it is always insert at first.
    # This is to avoid the codestral completion from suddenly replacing the
    # jedi completion that is shown already during the first (non-full) pass
    if jedi_completions:
        return [jedi_completions[0]] + codestral_completions + jedi_completions[1:]        
    return codestral_completions + jedi_completions


calltip = jedi.jedi_signatures
check = ruff.ruff_check
symbols = jedi.jedi_symbols
