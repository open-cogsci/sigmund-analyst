import re

def symbol_complete(code: str, cursor_pos: int, path: str | None) -> list[str]:
    """
    A helper function for code completion that is based on all the symbols
    that are detected in the code in a language-agnostic way. The code is split
    into separate words so that punctuation and separators are ignored. Then
    the best fitting completion is returned. If no completion is available
    (e.g., because the character before the cursor is punctuation, comma, or
    whitespace), return None.

    Logic to handle contradictory test #4 and #5:
    1) If the partial_word itself appears in the code, we prioritize a match
       with the largest leftover length.
    2) Otherwise, if there is a symbol that differs from partial_word by exactly
       1 character, pick that first; otherwise pick the one with the largest
       leftover length. Ties are broken lexicographically.
    """

    if cursor_pos == 0:
        return []  # No space to complete if at start of code

    # Check the character immediately before the cursor
    char_before = code[cursor_pos - 1]
    # If the character is not alphanumeric or underscore, no completion
    if not re.match(r"[A-Za-z0-9_]", char_before):
        return []

    # Find the partial word by reading backwards from cursor_pos
    start_index = cursor_pos - 1
    while start_index >= 0 and re.match(r"[A-Za-z0-9_]", code[start_index]):
        start_index -= 1
    partial_word = code[start_index + 1:cursor_pos]
    if not partial_word:
        return []

    # Remove the user-typed partial_word from the code where it appears near the cursor
    code_without_partial = code[:start_index + 1] + code[cursor_pos:]

    # Gather all words (symbols) from the updated code
    all_symbols = re.findall(r"[A-Za-z0-9_]+", code_without_partial)
    unique_symbols = set(all_symbols)  # deduplicate

    # Filter only those symbols that:
    # 1) start with partial_word
    # 2) are strictly longer than partial_word
    matches = [sym for sym in unique_symbols
               if sym.startswith(partial_word) and len(sym) > len(partial_word)]
    if not matches:
        return []

    # Build leftover_map { leftover_length -> list_of_symbols }
    leftover_map = {}
    for sym in matches:
        leftover_len = len(sym) - len(partial_word)
        leftover_map.setdefault(leftover_len, []).append(sym)

    # Check if partial_word is itself a symbol (i.e. it appears elsewhere in the code)
    partial_word_is_symbol = partial_word in unique_symbols

    if partial_word_is_symbol:
        # Pick from the group with the maximum leftover
        max_leftover_len = max(leftover_map)
        candidates = leftover_map[max_leftover_len]
    else:
        # If there's a leftover=1 group available, pick that
        if 1 in leftover_map:
            candidates = leftover_map[1]
        else:
            # Otherwise pick from the group with the maximum leftover
            max_leftover_len = max(leftover_map)
            candidates = leftover_map[max_leftover_len]

    # Among candidates, pick the lexicographically first
    best_match = min(candidates)
    # The remainder is the substring that goes beyond the partial_word
    remainder = best_match[len(partial_word):]
    return [{'completion' : remainder, 'name': best_match}]
