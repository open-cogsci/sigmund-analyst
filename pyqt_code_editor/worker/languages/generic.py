from ..providers import symbol, codestral, tree_sitter

def complete(code, cursor_pos, path, multiline, full, env_path, prefix):
    if full or multiline:
        completions = codestral.codestral_complete(
            code, cursor_pos, multiline=multiline, prefix=prefix)
    else:
        completions = []
    if not multiline:
        completions += symbol.symbol_complete(code, cursor_pos)
    return completions

calltip = None
check = None
symbols = None
matching_brackets = tree_sitter.tree_sitter_matching_brackets
