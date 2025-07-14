from ..providers import symbol, codestral

def complete(code, cursor_pos, path, multiline, full, env_path):
    if full or multiline:
        completions = codestral.codestral_complete(
            code, cursor_pos, multiline=multiline)
    else:
        completions = []
    if not multiline:
        completions += symbol.symbol_complete(code, cursor_pos)
    return completions

calltip = None
check = None
symbols = None
